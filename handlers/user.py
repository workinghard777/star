from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
import keyboards as kb
from config import cfg
from utils.prices import calc_price_usd, usd_to_ton, usd_to_trx, make_unique_amount

router = Router()


class BuyStates(StatesGroup):
    waiting_custom_amount = State()


WELCOME_TEXT = (
    "✨ <b>Star Market</b> — магазин Telegram Stars\n\n"
    "Покупайте звёзды по ценам, ориентированным на Fragment, "
    "с оплатой в TON или TRX и мгновенной автоматической проверкой платежа.\n\n"
    "Выберите действие:"
)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await db.upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(WELCOME_TEXT, reply_markup=kb.main_menu_kb())


@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(WELCOME_TEXT, reply_markup=kb.main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "buy")
async def buy_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "⭐ <b>Выберите количество Stars</b>\n\n"
        "Чем больше объём — тем выгоднее цена за звезду (как на Fragment)."
    )
    await call.message.edit_text(text, reply_markup=kb.amounts_kb())
    await call.answer()


@router.callback_query(F.data.startswith("amt:"))
async def amount_chosen(call: CallbackQuery, state: FSMContext):
    value = call.data.split(":", 1)[1]

    if value == "custom":
        await state.set_state(BuyStates.waiting_custom_amount)
        await call.message.edit_text(
            f"✏️ Введите количество Stars числом.\n"
            f"Диапазон: от {cfg.min_stars} до {cfg.max_stars}.",
            reply_markup=kb.back_kb("buy"),
        )
        await call.answer()
        return

    stars = int(value)
    await show_order_preview(call.message, stars, edit=True)
    await call.answer()


@router.message(StateFilter(BuyStates.waiting_custom_amount))
async def custom_amount_entered(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit():
        await message.answer("Пожалуйста, введите целое число.")
        return
    stars = int(text)
    if stars < cfg.min_stars or stars > cfg.max_stars:
        await message.answer(
            f"Количество должно быть от {cfg.min_stars} до {cfg.max_stars}. Попробуйте снова."
        )
        return
    await state.clear()
    await show_order_preview(message, stars, edit=False)


async def show_order_preview(message: Message, stars: int, edit: bool):
    """
    edit=True  -> вызвано из callback (правим существующее сообщение)
    edit=False -> вызвано из обычного текстового сообщения пользователя
                  (отправляем новое сообщение)

    Раньше здесь стояла проверка isinstance(message, Message), которая
    всегда была True в обоих случаях (call.message тоже имеет тип Message),
    из-за чего ветка edit_text была недостижима, и бот при выборе суммы
    кнопкой отправлял новое сообщение вместо редактирования старого.
    """
    price_usd = calc_price_usd(stars)
    ton_amount = usd_to_ton(price_usd)
    trx_amount = usd_to_trx(price_usd)
    text = (
        f"🧾 <b>Предварительный расчёт</b>\n\n"
        f"⭐ Количество: <b>{stars}</b>\n"
        f"💵 Стоимость: <b>${price_usd:.2f}</b>\n\n"
        f"💎 В TON: ≈ <b>{ton_amount}</b> TON\n"
        f"🔺 В TRX: ≈ <b>{trx_amount}</b> TRX\n\n"
        f"Выберите способ оплаты:"
    )
    if edit:
        await message.edit_text(text, reply_markup=kb.confirm_amount_kb(stars))
    else:
        await message.answer(text, reply_markup=kb.confirm_amount_kb(stars))


@router.callback_query(F.data.startswith("pay:"))
async def create_payment(call: CallbackQuery):
    _, currency, stars_str = call.data.split(":")
    stars = int(stars_str)
    price_usd = calc_price_usd(stars)

    # order_id генерируем заранее, т.к. для TRX точная сумма к оплате
    # (unique amount) зависит от самого order_id — так заказ создаётся
    # в БД сразу с финальной суммой, без "долечивания" отдельным UPDATE
    order_id = db.generate_order_id()

    if currency == "TON":
        base_amount = usd_to_ton(price_usd)
        wallet = cfg.ton_wallet
        pay_amount = base_amount  # для TON сопоставление в первую очередь по комментарию
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
        stars_amount=stars,
        price_usd=price_usd,
        currency=currency,
        pay_amount=pay_amount,
        wallet=wallet,
        order_id=order_id,
    )

    text = (
        f"💳 <b>Заказ #{order_id}</b>\n\n"
        f"⭐ Stars: <b>{stars}</b>\n"
        f"💵 Сумма: <b>${price_usd:.2f}</b>\n"
        f"💰 К оплате: <b>{pay_amount} {currency}</b>\n\n"
        f"📥 Кошелёк для перевода:\n<code>{wallet}</code>\n"
        f"{memo_hint}\n"
        f"⏳ Заказ действителен {cfg.payment_timeout_minutes} минут.\n"
        f"После перевода нажмите «Проверить оплату» — платёж подтвердится автоматически."
    )
    await call.message.edit_text(text, reply_markup=kb.order_check_kb(order_id))
    await call.answer()


@router.callback_query(F.data.startswith("check:"))
async def check_payment(call: CallbackQuery, bot: Bot):
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return

    if order["status"] == "awaiting_payment":
        await call.answer("⏳ Платёж пока не найден. Проверка выполняется автоматически каждые "
                           f"{cfg.poll_interval_seconds} сек, попробуйте чуть позже.", show_alert=True)
        return
    if order["status"] in ("paid", "delivered"):
        await call.message.edit_text(
            f"✅ Заказ #{order_id} оплачен!\n\n"
            f"⭐ {order['stars_amount']} Stars уже переданы в обработку.\n"
            f"Если звёзды не пришли в течение часа — напишите в поддержку.",
        )
        await call.answer()
        return
    if order["status"] == "expired":
        await call.answer("⌛ Срок действия заказа истёк. Оформите новый.", show_alert=True)
        return
    if order["status"] == "cancelled":
        await call.answer("Заказ отменён.", show_alert=True)


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_order_cb(call: CallbackQuery):
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order or order["status"] != "awaiting_payment":
        await call.answer("Заказ нельзя отменить.", show_alert=True)
        return
    await db.set_order_status(order_id, "cancelled")
    await call.message.edit_text(f"❌ Заказ #{order_id} отменён.", reply_markup=kb.main_menu_kb())
    await call.answer()


@router.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    mine = await db.get_orders_by_user(call.from_user.id, limit=10)
    if not mine:
        await call.message.edit_text("У вас пока нет заказов.", reply_markup=kb.back_kb())
        await call.answer()
        return
    status_emoji = {
        "awaiting_payment": "⏳", "paid": "✅", "delivered": "📦",
        "expired": "⌛", "cancelled": "❌",
    }
    lines = ["📦 <b>Ваши заказы</b>\n"]
    for o in mine:
        item_desc = f"{o['stars_amount']}⭐" if o["kind"] == "stars" else o["item_title"]
        lines.append(
            f"{status_emoji.get(o['status'], '•')} #{o['order_id']} — {item_desc} "
            f"— ${o['price_usd']:.2f} ({o['status']})"
        )
    await call.message.edit_text("\n".join(lines), reply_markup=kb.back_kb())
    await call.answer()
