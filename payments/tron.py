"""
Проверка входящих TRX-платежей через TronGrid API.

TRON-переводы (native TRX) не имеют удобного поля memo для рядовых кошельков,
поэтому сопоставление заказа с платежом идёт по точной сумме с уникальным
"хвостом" (см. utils.prices.make_unique_amount).
"""
import aiohttp
from config import cfg

TRONGRID_URL = "https://api.trongrid.io/v1/accounts/{address}/transactions"

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_to_hex(address: str) -> str:
    """
    Конвертирует TRON-адрес из base58check (напр. "TXYZ...") в hex-адрес
    (напр. "41..."), в котором TronGrid возвращает owner_address/to_address.
    Нужно, чтобы надёжно проверять, что платёж пришёл именно НА наш кошелёк,
    а не с него (раньше это никак не проверялось и совпадение шло только
    по сумме, что могло ложно сработать на исходящей транзакции).
    """
    num = 0
    for char in address:
        num = num * 58 + _B58_ALPHABET.index(char)
    combined = num.to_bytes(25, byteorder="big")
    return combined[:-4].hex()  # отбрасываем 4-байтный чек-код


_OUR_WALLET_HEX = None


def _our_wallet_hex() -> str:
    global _OUR_WALLET_HEX
    if _OUR_WALLET_HEX is None:
        try:
            _OUR_WALLET_HEX = base58_to_hex(cfg.trx_wallet)
        except Exception:
            _OUR_WALLET_HEX = ""
    return _OUR_WALLET_HEX


async def fetch_incoming_transactions(limit: int = 30):
    url = TRONGRID_URL.format(address=cfg.trx_wallet)
    params = {"limit": limit, "only_confirmed": "true", "order_by": "block_timestamp,desc"}
    headers = {}
    if cfg.trongrid_api_key:
        headers["TRON-PRO-API-KEY"] = cfg.trongrid_api_key

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=15) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            return data.get("data", [])


def _extract_amount_trx(tx: dict) -> float:
    try:
        contract = tx["raw_data"]["contract"][0]
        if contract["type"] != "TransferContract":
            return 0.0
        value = contract["parameter"]["value"].get("amount", 0)
        return value / 1e6
    except Exception:
        return 0.0


def _extract_to(tx: dict) -> str:
    try:
        contract = tx["raw_data"]["contract"][0]
        return (contract["parameter"]["value"].get("to_address", "") or "").lower()
    except Exception:
        return ""


async def find_matching_payment(expected_amount: float, tolerance: float = 0.000001):
    wallet_hex = _our_wallet_hex()
    txs = await fetch_incoming_transactions()
    for tx in txs:
        amount = _extract_amount_trx(tx)
        tx_hash = tx.get("txID", "")
        if not tx_hash or amount <= 0:
            continue
        # если удалось получить hex нашего кошелька — проверяем направление,
        # чтобы случайно не засчитать исходящий перевод с этого же аккаунта
        if wallet_hex and _extract_to(tx) not in ("", wallet_hex.lower()):
            continue
        if abs(amount - expected_amount) <= tolerance:
            return tx_hash
    return None
