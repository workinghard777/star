"""
Каталог "удалённых" (снятых с текущей витрины) обычных подарков Telegram
и тарифов Telegram Premium.

Это не лимитированные NFT-гифты, а обычные gift-стикеры, которые Telegram
когда-то продавал в общем магазине и затем убрал оттуда, но они по-прежнему
пересылаются между пользователями по числовому gift_id через API
(payments.sendStarGift / payments.transferStarGift), если этот ID есть
в наличии у отправителя.

ВАЖНО: gift_id ниже — ЗАГЛУШКИ (0). Перед реальной выдачей подставьте туда
настоящие числовые ID из вашего инвентаря (payments.getSavedStarGifts на
аккаунте, где эти подарки есть). Это единственное, что нужно донастроить
руками — сама покупка/оплата/уведомление админу работают и без этого.
"""

GIFTS = [
    {"key": "ny_tree",        "gift_id": 0, "emoji": "🎄", "title": "Новогодняя ёлочка",  "price_usd": 0.84},
    {"key": "ny_bear",        "gift_id": 0, "emoji": "🧸", "title": "Новогодний мишка",    "price_usd": 0.84},
    {"key": "heart_love",     "gift_id": 0, "emoji": "💝", "title": "Сердце Влюблённых",   "price_usd": 0.84},
    {"key": "bear_love",      "gift_id": 0, "emoji": "🐻", "title": "Мишка Влюблённых",    "price_usd": 0.84},
    {"key": "bear_8march",    "gift_id": 0, "emoji": "💐", "title": "Мишка 8-е марта",     "price_usd": 0.84},
    {"key": "bear_patrick",   "gift_id": 0, "emoji": "🍀", "title": "Мишка Патрика",       "price_usd": 0.84},
    {"key": "bear_april1",    "gift_id": 0, "emoji": "🎉", "title": "Мишка 1-е апреля",    "price_usd": 0.84},
    {"key": "bear_easter",    "gift_id": 0, "emoji": "🐰", "title": "Пасхальный мишка",    "price_usd": 0.84},
    {"key": "bear_worker",    "gift_id": 0, "emoji": "🔨", "title": "Мишка работяга",      "price_usd": 0.84},
    {"key": "bear_champion",  "gift_id": 0, "emoji": "⚽", "title": "Мишка чемпион",       "price_usd": 0.84},
    {"key": "bear_terrorist", "gift_id": 0, "emoji": "💣", "title": "Мишка террорист",     "price_usd": 0.84},
]

PREMIUM_PLANS = [
    {"key": "p3",  "months": 3,  "title": "3 месяца",   "price_usd": 13.0},
    {"key": "p6",  "months": 6,  "title": "6 месяцев",  "price_usd": 18.0},
    {"key": "p12", "months": 12, "title": "12 месяцев", "price_usd": 32.0},
]


def get_gift(key: str):
    return next((g for g in GIFTS if g["key"] == key), None)


def get_plan(key: str):
    return next((p for p in PREMIUM_PLANS if p["key"] == key), None)
