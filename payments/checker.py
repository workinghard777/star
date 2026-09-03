import asyncio
import logging
from aiogram import Bot

import database as db
from config import cfg
from payments import ton, tron
from handlers.admin import notify_admin_new_order

log = logging.getLogger("payments.checker")


async def deliver_stars(order) -> bool:
    """
    Заглушка для фактической выдачи звёзд пользователю.

    Реальная выдача Telegram Stars стороннему пользователю не выполняется
    через обычный Bot API — обычно это делается через Fragment (TON-контракт)
    либо отдельный аккаунт с доступом к покупке звёзд на конкретный @username.

    Подключите здесь вызов вашей интеграции с Fragment (FRAGMENT_SESSION_COOKIE
    в .env), если она у вас есть. Пока интеграция не настроена — возвращаем
    False, и заказ остаётся в статусе "paid" с уведомлением админу для
    ручной/полуавтоматической выдачи.
    """
    if not cfg.fragment_session_cookie:
        return False
    # TODO: интеграция с Fragment API
    return False


async def process_paid_order(bot: Bot, order_id: str):
    order = await db.get_order(order_id)
    if not order:
        return
    await notify_admin_new_order(bot, order)

    delivered = await deliver_stars(order)
    if delivered:
        await db.set_order_status(order_id, "delivered")
        try:
            await bot.send_message(
                order["user_id"],
                f"🎉 Заказ #{order_id} выполнен! {order['stars_amount']}⭐ зачислены.",
            )
        except Exception:
            pass
    else:
        try:
            await bot.send_message(
                order["user_id"],
                f"✅ Оплата заказа #{order_id} подтверждена!\n"
                f"⭐ Ваши {order['stars_amount']} Stars уже обрабатываются, "
                f"это может занять немного времени.",
            )
        except Exception:
            pass


async def check_ton_orders(bot: Bot):
    orders = await db.get_awaiting_orders(currency="TON")
    for order in orders:
        tx_hash = await ton.find_matching_payment(order["order_id"], order["pay_amount"])
        if tx_hash:
            ok = await db.mark_order_paid(order["order_id"], tx_hash)
            if ok:
                await process_paid_order(bot, order["order_id"])


async def check_trx_orders(bot: Bot):
    orders = await db.get_awaiting_orders(currency="TRX")
    for order in orders:
        tx_hash = await tron.find_matching_payment(order["pay_amount"])
        if tx_hash:
            ok = await db.mark_order_paid(order["order_id"], tx_hash)
            if ok:
                await process_paid_order(bot, order["order_id"])


async def payment_polling_loop(bot: Bot):
    log.info("Payment polling loop started")
    while True:
        try:
            await check_ton_orders(bot)
            await check_trx_orders(bot)
            await db.expire_stale_orders()
        except Exception as e:
            log.exception("Error in payment polling loop: %s", e)
        await asyncio.sleep(cfg.poll_interval_seconds)
