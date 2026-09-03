from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

import catalog
import database as db
import keyboards as kb
from config import cfg
from utils.prices import usd_to_ton, usd_to_trx, make_unique_amount

router = Router()


@router.callback_query(F.data == "gifts_menu")
async def gifts_menu(call: CallbackQuery):
    text = (
        "🎁 <b>Покупка подарков</b>\n\n"
        "Здесь вы можете купить лимитированные подарки, "
        "которые уже удалены из общего магазина Telegram\n\n"
        "<i>Выберите подарок из списка ниже</i>"
    )
    await call.message.edit_text(text, reply_markup=kb.gifts_kb())
    await call.answer()


@router.callback_query(F.data.startswith("gift:"))
async def gift_chosen(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    gift = catalog.get_gift(key)
    if not gift:
        await call.answer("Подарок не найден", show_alert=True)
        return
    text = (
        f"{gift['emoji']} <b>{gift['title']}</b>\n\n"
        f"💵 Цена: <b>${gift['price_usd']:.2f}</b>\n\n"
        f"Выберите способ оплаты:"
    )
    await call.message.edit_text(text, reply_markup=kb.gift_pay_kb(key))
    await call.answer()


@router.callback_query(F.data.startswith("gpay:"))
async def gift_pay(call: CallbackQuery):
    _, currency, key = call.data.split(":")
    gift = catalog.get_gift(key)
    if not gift:
        await call.answer("Подарок не найден", show_alert=True)
        return

    order_id = db.generate_order_id()
    price_usd = gift["price_usd"]

    if currency == "TON":
        base_amount = usd_to_ton(price_usd)
        wallet = cfg.ton_wallet
        pay_amount = base_amount
        memo_hint = f"\n📝 <b>Обязательно укажите комментарий к переводу:</b>\n<code>{order_id}</code>\n"
    else:
        base_amount = usd_to_trx(price_usd)
        wallet = cfg.trx_wallet
        pay_amount = make_unique_amount(base_amount, order_id)
        memo_hint = (
            "\n⚠️ <b>Переведите сумму ТОЧНО как указано ниже</b> "
            "(с учётом всех знаков после запятой) — это нужно для автоматического "
            "распознавания вашего платежа.\n"
        )

    await db.create_order(
        user_id=call.from_user.id,
        username=call.from_user.username,
        stars_amount=None,
        price_usd=price_usd,
        currency=currency,
        pay_amount=pay_amount,
        wallet=wallet,
        order_id=order_id,
        kind="gift",
        item_key=key,
        item_title=f"{gift['emoji']} {gift['title']}",
    )

    text = (
        f"💳 <b>Заказ #{order_id}</b>\n\n"
        f"{gift['emoji']} Товар: <b>{gift['title']}</b>\n"
        f"💵 Сумма: <b>${price_usd:.2f}</b>\n"
        f"💰 К оплате: <b>{pay_amount} {currency}</b>\n\n"
        f"📥 Кошелёк для перевода:\n<code>{wallet}</code>\n"
        f"{memo_hint}\n"
        f"⏳ Заказ действителен {cfg.payment_timeout_minutes} минут.\n"
        f"После перевода нажмите «Проверить оплату»."
    )
    await call.message.edit_text(text, reply_markup=kb.extra_order_check_kb(order_id))
    await call.answer()


# Общие для gift/premium — работают по orders независимо от kind
@router.callback_query(F.data.startswith("gcheck:"))
async def extra_check_payment(call: CallbackQuery, bot: Bot):
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    if order["status"] == "awaiting_payment":
        await call.answer(
            "⏳ Платёж пока не найден. Проверка выполняется автоматически каждые "
            f"{cfg.poll_interval_seconds} сек, попробуйте чуть позже.", show_alert=True)
        return
    if order["status"] in ("paid", "delivered"):
        await call.message.edit_text(
            f"✅ Заказ #{order_id} оплачен!\n\n"
            f"Товар «{order['item_title']}» передан в обработку и будет выслан вам вручную "
            f"в ближайшее время.\nЕсли ничего не пришло в течение часа — напишите в поддержку.",
        )
        await call.answer()
        return
    if order["status"] == "expired":
        await call.answer("⌛ Срок действия заказа истёк. Оформите новый.", show_alert=True)
        return
    if order["status"] == "cancelled":
        await call.answer("Заказ отменён.", show_alert=True)


@router.callback_query(F.data.startswith("gcancel:"))
async def extra_cancel_order(call: CallbackQuery):
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order or order["status"] != "awaiting_payment":
        await call.answer("Заказ нельзя отменить.", show_alert=True)
        return
    await db.set_order_status(order_id, "cancelled")
    await call.message.edit_text(f"❌ Заказ #{order_id} отменён.", reply_markup=kb.main_menu_kb())
    await call.answer()
