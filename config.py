import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass
class Config:
    bot_token: str = _env("BOT_TOKEN")
    admin_id: int = int(_env("ADMIN_ID", "8804040519"))
    support_username: str = _env("SUPPORT_USERNAME", "vednesty")

    ton_wallet: str = _env("TON_WALLET")
    trx_wallet: str = _env("TRX_WALLET")

    toncenter_api_key: str = _env("TONCENTER_API_KEY")
    trongrid_api_key: str = _env("TRONGRID_API_KEY")

    ton_usd_rate: float = float(_env("TON_USD_RATE", "5.8"))
    trx_usd_rate: float = float(_env("TRX_USD_RATE", "0.27"))

    db_path: str = _env("DB_PATH", "stars_shop.db")

    fragment_session_cookie: str = _env("FRAGMENT_SESSION_COOKIE")
    fragment_api_hash: str = _env("FRAGMENT_API_HASH")

    # Базовая цена за 1 звезду в USD (ориентир на Fragment).
    # Fragment продаёт пакетами с небольшой скидкой на объёме — это отражено
    # в PRICE_TIERS ниже. Значения можно менять из админ-панели (/admin -> Настройки).
    base_price_per_star_usd: float = 0.0155

    # Пороговые скидки по объёму (кол-во звёзд -> цена за штуку в USD)
    price_tiers: tuple = (
        (50, 0.0165),
        (100, 0.0160),
        (500, 0.0155),
        (1000, 0.0150),
        (5000, 0.0145),
        (10000, 0.0140),
    )

    min_stars: int = 50
    max_stars: int = 1_000_000

    # Таймаут ожидания оплаты (минуты)
    payment_timeout_minutes: int = 30

    # Интервал опроса блокчейнов (секунды)
    poll_interval_seconds: int = 20


cfg = Config()
