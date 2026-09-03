import asyncio
import logging
from aiogram import Bot

import database as db
from config import cfg
from payments import ton, tron
from handlers.admin import notify_admin_extra_order

log = logging.getLogger("payments.checker_extra")

EXTRA_KINDS = ("gift", "premium")


async def process_paid_extra_order(bot: Bot, order_id: str):
    order = await db.get_order(order_id)
    if not order:
        return
    await notify_admin_extra_order(bot, order)
    try:
        await bot.send_message(
            order["user_id"],
            f"✅ Оплата заказа #{order_id} подтверждена!\n"
            f"Товар «{order['item_title']}» передан в обработку, "
            f"мы вышлем его вручную в ближайшее время.",
        )
    except Exception:
        pass


async def check_ton_extra_orders(bot: Bot):
    orders = await db.get_awaiting_orders(currency="TON", kind=EXTRA_KINDS)
    for order in orders:
        tx_hash = await ton.find_matching_payment(order["order_id"], order["pay_amount"])
        if tx_hash:
            ok = await db.mark_order_paid(order["order_id"], tx_hash)
            if ok:
                await process_paid_extra_order(bot, order["order_id"])


async def check_trx_extra_orders(bot: Bot):
    orders = await db.get_awaiting_orders(currency="TRX", kind=EXTRA_KINDS)
    for order in orders:
        tx_hash = await tron.find_matching_payment(order["pay_amount"])
        if tx_hash:
            ok = await db.mark_order_paid(order["order_id"], tx_hash)
            if ok:
                await process_paid_extra_order(bot, order["order_id"])


async def extra_payment_polling_loop(bot: Bot):
    """
    Отдельная задача только для poll'а gift/premium заказов. db.expire_stale_orders()
    здесь не вызывается — она уже вызывается в payments/checker.py's
    payment_polling_loop() и не фильтрует по kind, так что заказы всех типов
    (включая gift/premium) истекают там; повторный вызов тут был бы избыточным.
    """
    log.info("Extra payment polling loop started")
    while True:
        try:
            await check_ton_extra_orders(bot)
            await check_trx_extra_orders(bot)
        except Exception as e:
            log.exception("Error in extra payment polling loop: %s", e)
        await asyncio.sleep(cfg.poll_interval_seconds)
