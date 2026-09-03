from aiogram import Router, F
from aiogram.types import CallbackQuery

import catalog
import database as db
import keyboards as kb
from config import cfg
from utils.prices import usd_to_ton, usd_to_trx, make_unique_amount

router = Router()


@router.callback_query(F.data == "premium_menu")
async def premium_menu(call: CallbackQuery):
    text = (
        "🔥 <b>Покупка Telegram Premium</b>\n\n"
        "Оформляется на ваш аккаунт (username, с которого вы пишете боту).\n\n"
        "<i>Выберите срок подписки:</i>"
    )
    await call.message.edit_text(text, reply_markup=kb.premium_kb())
    await call.answer()


@router.callback_query(F.data.startswith("prem:"))
async def plan_chosen(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    plan = catalog.get_plan(key)
    if not plan:
        await call.answer("Тариф не найден", show_alert=True)
        return
    text = (
        f"🔥 <b>Telegram Premium — {plan['title']}</b>\n\n"
        f"💵 Цена: <b>${plan['price_usd']:.2f}</b>\n\n"
        f"Выберите способ оплаты:"
    )
    await call.message.edit_text(text, reply_markup=kb.premium_pay_kb(key))
    await call.answer()


@router.callback_query(F.data.startswith("prempay:"))
async def premium_pay(call: CallbackQuery):
    _, currency, key = call.data.split(":")
    plan = catalog.get_plan(key)
    if not plan:
        await call.answer("Тариф не найден", show_alert=True)
        return

    order_id = db.generate_order_id()
    price_usd = plan["price_usd"]
    item_title = f"Telegram Premium — {plan['title']}"

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
        kind="premium",
        item_key=key,
        item_title=item_title,
    )

    text = (
        f"💳 <b>Заказ #{order_id}</b>\n\n"
        f"🔥 Товар: <b>{item_title}</b>\n"
        f"💵 Сумма: <b>${price_usd:.2f}</b>\n"
        f"💰 К оплате: <b>{pay_amount} {currency}</b>\n\n"
        f"📥 Кошелёк для перевода:\n<code>{wallet}</code>\n"
        f"{memo_hint}\n"
        f"⏳ Заказ действителен {cfg.payment_timeout_minutes} минут.\n"
        f"После перевода нажмите «Проверить оплату»."
    )
    await call.message.edit_text(text, reply_markup=kb.extra_order_check_kb(order_id))
    await call.answer()

# Проверка/отмена заказа — общие хендлеры gcheck:/gcancel: уже зарегистрированы
# в handlers/gifts.py и работают по orders независимо от kind,
# поэтому здесь их дублировать не нужно.
