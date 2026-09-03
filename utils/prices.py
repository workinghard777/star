from config import cfg


def price_per_star(stars: int) -> float:
    """Возвращает цену за 1 звезду в USD с учётом объёмной скидки."""
    price = cfg.base_price_per_star_usd
    for threshold, tier_price in cfg.price_tiers:
        if stars >= threshold:
            price = tier_price
    return price


def calc_price_usd(stars: int) -> float:
    return round(stars * price_per_star(stars), 4)


def usd_to_ton(amount_usd: float) -> float:
    return round(amount_usd / cfg.ton_usd_rate, 6)


def usd_to_trx(amount_usd: float) -> float:
    return round(amount_usd / cfg.trx_usd_rate, 6)


def make_unique_amount(base_amount: float, order_id: str, decimals: int = 6) -> float:
    """
    Добавляет к сумме уникальный "хвост", вычисленный из order_id,
    чтобы отличать платежи друг от друга, когда мемо/комментарий
    недоступен (актуально для TRX/TRON).

    Хвост должен быть исчезающе малым (сотые/тысячные доли цента), а не
    ощутимой добавкой к сумме. Раньше формула ошибочно добавляла 1-10 TRX
    (то есть реально удорожала заказ на $0.3-$2.7) — исправлено: теперь
    добавка лежит в диапазоне 0.0001-0.0009 TRX.

    Раньше хвост брался как int(order_id[-6:], 16) % 900 — для похожих
    id (например, отличающихся на 1 в последнем разряде, как это бывает
    при последовательной генерации в тестах) это давало коллизии, т.к.
    соседние числа почти всегда попадают в один и тот же остаток от 900.
    Теперь используется sha256-хэш всего order_id, что даёт равномерный
    и непредсказуемый разброс даже для близких id.
    """
    import hashlib
    digest = hashlib.sha256(order_id.encode()).hexdigest()
    tail = int(digest[:8], 16) % 900 + 100  # 100..999
    # offset должен быть виден на разрядности decimals, иначе он "теряется"
    # при round(...). При decimals=6 это даёт диапазон 0.0001..0.000999 —
    # именно так и было задумано (ранее из-за лишнего множителя 10**3 смещение
    # было на 3 порядка меньше разрешения округления и просто исчезало).
    offset = tail / 10 ** decimals
    return round(base_amount + offset, decimals)
