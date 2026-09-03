import time
import uuid
import aiosqlite
from config import cfg

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_seen INTEGER,
    orders_count INTEGER DEFAULT 0,
    total_spent_usd REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    user_id INTEGER,
    username TEXT,
    stars_amount INTEGER,
    price_usd REAL,
    currency TEXT,               -- 'TON' or 'TRX'
    pay_amount REAL,             -- exact amount incl. disambiguation offset
    wallet TEXT,
    status TEXT,                 -- awaiting_payment, paid, delivered, expired, cancelled
    tx_hash TEXT,
    created_at INTEGER,
    updated_at INTEGER,
    kind TEXT DEFAULT 'stars',   -- 'stars' | 'gift' | 'premium'
    item_key TEXT,               -- ключ товара из catalog.py (для gift/premium)
    item_title TEXT              -- отображаемое название товара (для gift/premium)
);

CREATE TABLE IF NOT EXISTS processed_tx (
    tx_hash TEXT PRIMARY KEY,
    order_id TEXT,
    processed_at INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

# Колонки kind/item_key/item_title добавлены позже. Для БД, созданных до этого
# изменения, CREATE TABLE IF NOT EXISTS их не добавит (таблица orders уже
# существует) — поэтому дополнительно догоняем схему через ALTER TABLE.
# SQLite не поддерживает "ADD COLUMN IF NOT EXISTS", поэтому просто игнорируем
# ошибку "duplicate column", если колонка уже есть.
_MIGRATIONS = (
    "ALTER TABLE orders ADD COLUMN kind TEXT DEFAULT 'stars'",
    "ALTER TABLE orders ADD COLUMN item_key TEXT",
    "ALTER TABLE orders ADD COLUMN item_title TEXT",
)


async def init_db():
    async with aiosqlite.connect(cfg.db_path) as db:
        await db.executescript(SCHEMA)
        for stmt in _MIGRATIONS:
            try:
                await db.execute(stmt)
            except Exception:
                pass  # колонка уже существует
        await db.commit()


async def upsert_user(user_id: int, username: str | None):
    async with aiosqlite.connect(cfg.db_path) as db:
        await db.execute(
            """INSERT INTO users (user_id, username, first_seen)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET username=excluded.username""",
            (user_id, username or "", int(time.time())),
        )
        await db.commit()


def generate_order_id() -> str:
    return uuid.uuid4().hex[:10].upper()


async def create_order(user_id, username, stars_amount, price_usd, currency, pay_amount, wallet,
                        order_id: str | None = None, kind: str = "stars",
                        item_key: str | None = None, item_title: str | None = None) -> str:
    """
    Если order_id не передан — генерируется автоматически. Явная передача
    нужна, когда точная сумма к оплате (pay_amount) сама зависит от
    order_id (см. utils.prices.make_unique_amount для TRX) — тогда id
    генерируют заранее через generate_order_id() и передают сюда вместе
    с уже посчитанной суммой, вместо создания заказа с pay_amount=0
    и последующего "долечивания" отдельным UPDATE-запросом.

    kind='stars' (по умолчанию) — обычная покупка звёзд, stars_amount обязателен.
    kind='gift'/'premium' — заказ подарка/Premium из catalog.py; stars_amount
    в этом случае не используется и остаётся NULL, а item_key/item_title
    описывают конкретный товар.
    """
    if order_id is None:
        order_id = generate_order_id()
    now = int(time.time())
    async with aiosqlite.connect(cfg.db_path) as db:
        await db.execute(
            """INSERT INTO orders
               (order_id, user_id, username, stars_amount, price_usd, currency,
                pay_amount, wallet, status, tx_hash, created_at, updated_at,
                kind, item_key, item_title)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'awaiting_payment', NULL, ?, ?, ?, ?, ?)""",
            (order_id, user_id, username or "", stars_amount, price_usd, currency,
             pay_amount, wallet, now, now, kind, item_key, item_title),
        )
        await db.commit()
    return order_id


async def get_order(order_id: str):
    async with aiosqlite.connect(cfg.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE order_id=?", (order_id,))
        return await cur.fetchone()


async def get_awaiting_orders(currency: str | None = None, kind="stars"):
    """
    kind по умолчанию = 'stars' — это сохраняет прежнее поведение для
    payments/checker.py (он вызывает эту функцию без параметра kind и не
    должен получать заказы на подарки/Premium вперемешку со Stars).

    kind=None — без фильтра по типу (все заказы).
    kind — можно передать список/кортеж, чтобы получить сразу несколько
    типов, например kind=("gift", "premium").
    """
    async with aiosqlite.connect(cfg.db_path) as db:
        db.row_factory = aiosqlite.Row
        conditions = ["status='awaiting_payment'"]
        params: list = []
        if currency:
            conditions.append("currency=?")
            params.append(currency)
        if kind is not None:
            if isinstance(kind, (list, tuple, set)):
                placeholders = ",".join("?" for _ in kind)
                conditions.append(f"kind IN ({placeholders})")
                params.extend(kind)
            else:
                conditions.append("kind=?")
                params.append(kind)
        query = "SELECT * FROM orders WHERE " + " AND ".join(conditions)
        cur = await db.execute(query, params)
        return await cur.fetchall()


async def mark_order_paid(order_id: str, tx_hash: str):
    now = int(time.time())
    async with aiosqlite.connect(cfg.db_path) as db:
        db.row_factory = aiosqlite.Row
        # Идемпотентность: если tx_hash уже обработан — не засчитываем повторно.
        # Это единственная защита от двойной обработки одной транзакции —
        # INSERT ниже упадёт/не даст дублей благодаря PRIMARY KEY на tx_hash,
        # но мы проверяем заранее, чтобы не задваивать статистику пользователя.
        cur = await db.execute("SELECT 1 FROM processed_tx WHERE tx_hash=?", (tx_hash,))
        if await cur.fetchone():
            return False

        # Заказ не должен быть уже оплачен/обработан ранее (защита от гонки
        # между несколькими циклами опроса) и должен существовать.
        order = await (await db.execute(
            "SELECT * FROM orders WHERE order_id=?", (order_id,)
        )).fetchone()
        if not order or order["status"] != "awaiting_payment":
            return False

        try:
            await db.execute(
                "INSERT INTO processed_tx (tx_hash, order_id, processed_at) VALUES (?, ?, ?)",
                (tx_hash, order_id, now),
            )
        except Exception:
            # tx_hash уже кем-то вставлен параллельно — не обрабатываем повторно
            return False

        await db.execute(
            "UPDATE orders SET status='paid', tx_hash=?, updated_at=? WHERE order_id=?",
            (tx_hash, now, order_id),
        )
        await db.execute(
            "UPDATE users SET orders_count = orders_count + 1, total_spent_usd = total_spent_usd + ? WHERE user_id=?",
            (order["price_usd"], order["user_id"]),
        )
        await db.commit()
        return True


async def set_order_status(order_id: str, status: str):
    async with aiosqlite.connect(cfg.db_path) as db:
        await db.execute(
            "UPDATE orders SET status=?, updated_at=? WHERE order_id=?",
            (status, int(time.time()), order_id),
        )
        await db.commit()


async def expire_stale_orders():
    cutoff = int(time.time()) - cfg.payment_timeout_minutes * 60
    async with aiosqlite.connect(cfg.db_path) as db:
        await db.execute(
            "UPDATE orders SET status='expired', updated_at=? WHERE status='awaiting_payment' AND created_at < ?",
            (int(time.time()), cutoff),
        )
        await db.commit()


async def get_stats():
    async with aiosqlite.connect(cfg.db_path) as db:
        db.row_factory = aiosqlite.Row
        users = (await (await db.execute("SELECT COUNT(*) c FROM users")).fetchone())["c"]
        orders_total = (await (await db.execute("SELECT COUNT(*) c FROM orders")).fetchone())["c"]
        orders_paid = (await (await db.execute(
            "SELECT COUNT(*) c FROM orders WHERE status IN ('paid','delivered')"
        )).fetchone())["c"]
        revenue = (await (await db.execute(
            "SELECT COALESCE(SUM(price_usd),0) s FROM orders WHERE status IN ('paid','delivered')"
        )).fetchone())["s"]
        stars_sold = (await (await db.execute(
            "SELECT COALESCE(SUM(stars_amount),0) s FROM orders WHERE status IN ('paid','delivered')"
        )).fetchone())["s"]
        return {
            "users": users,
            "orders_total": orders_total,
            "orders_paid": orders_paid,
            "revenue_usd": revenue,
            "stars_sold": stars_sold,
        }


async def get_orders_by_user(user_id: int, limit: int = 10):
    async with aiosqlite.connect(cfg.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        return await cur.fetchall()


async def list_recent_orders(limit: int = 15):
    async with aiosqlite.connect(cfg.db_path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return await cur.fetchall()


async def get_setting(key: str, default: str = None):
    async with aiosqlite.connect(cfg.db_path) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(cfg.db_path) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()
