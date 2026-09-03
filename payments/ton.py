"""
Проверка входящих TON-платежей через TonCenter API.

Логика сопоставления заказа с платежом:
1) Приоритет — комментарий (text comment) в транзакции равен order_id.
   Это самый надёжный способ, TON поддерживает комментарии "из коробки".
2) Резерв — точное совпадение суммы (с уникальным "хвостом", см. utils.prices).
"""
import base64
import aiohttp
from config import cfg

TONCENTER_URL = "https://toncenter.com/api/v2/getTransactions"


async def fetch_incoming_transactions(limit: int = 30):
    params = {
        "address": cfg.ton_wallet,
        "limit": limit,
        "archival": "false",
    }
    headers = {}
    if cfg.toncenter_api_key:
        headers["X-API-Key"] = cfg.toncenter_api_key

    async with aiohttp.ClientSession() as session:
        async with session.get(TONCENTER_URL, params=params, headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data.get("result", [])


def _extract_comment(tx: dict) -> str:
    """
    TonCenter отдаёт текстовый комментарий в msg_data.text в виде base64
    от "сырых" байт сообщения (обычно с 4-байтным нулевым префиксом-опкодом
    простого текстового комментария). Раньше здесь сравнивалась base64-строка
    напрямую с order_id, из-за чего сопоставление по комментарию никогда
    не срабатывало — это исправлено.
    """
    try:
        msg = tx["in_msg"]
        raw_text = msg.get("msg_data", {}).get("text")
        if raw_text:
            decoded = base64.b64decode(raw_text)
            if decoded[:4] == b"\x00\x00\x00\x00":
                decoded = decoded[4:]
            return decoded.decode("utf-8", errors="ignore").strip()
        # некоторые ответы/версии API отдают уже декодированный comment
        return (msg.get("message") or "").strip()
    except Exception:
        return ""


def _extract_amount_ton(tx: dict) -> float:
    try:
        nanotons = int(tx["in_msg"]["value"])
        return nanotons / 1e9
    except Exception:
        return 0.0


def _extract_hash(tx: dict) -> str:
    return tx.get("transaction_id", {}).get("hash", "")


async def find_matching_payment(order_id: str, expected_amount: float, tolerance: float = 0.0005):
    """
    Возвращает tx_hash, если найдена подходящая входящая транзакция, иначе None.
    """
    txs = await fetch_incoming_transactions()
    for tx in txs:
        comment = _extract_comment(tx)
        amount = _extract_amount_ton(tx)
        tx_hash = _extract_hash(tx)
        if not tx_hash or amount <= 0:
            continue

        if comment == order_id:
            return tx_hash

        if abs(amount - expected_amount) <= tolerance:
            return tx_hash

    return None
