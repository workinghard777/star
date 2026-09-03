from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

import database as db
import keyboards as kb
from config import cfg

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == cfg.admin_id


# Скрытая админ-команда — не выводится в список команд бота (setMyCommands её не содержит)
@router.message(Command("admin_x8k2"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return  # молча игнорируем для всех остальных
    await message.answer(
        "🛠 <b>Панель администратора</b>\nStar Market",
        reply_markup=kb.admin_menu_kb(),
    )


@router.callback_query(F.data == "a_stats")
async def a_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    s = await db.get_stats()
    text = (
        "📊 <b>Статистика магазина</b>\n\n"
        f"👥 Пользователей: {s['users']}\n"
        f"🧾 Заказов всего: {s['orders_total']}\n"
        f"✅ Оплаченных заказов: {s['orders_paid']}\n"
        f"⭐ Продано звёзд: {s['stars_sold']}\n"
        f"💵 Выручка: ${s['revenue_usd']:.2f}\n"
    )
    await call.message.edit_text(text, reply_markup=kb.admin_menu_kb())
    await call.answer()


@router.callback_query(F.data == "a_orders")
async def a_orders(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    orders = await db.list_recent_orders(limit=10)
    if not orders:
        await call.message.edit_text("Заказов пока нет.", reply_markup=kb.admin_menu_kb())
        await call.answer()
        return
    lines = ["📋 <b>Последние заказы</b>\n"]
    for o in orders:
        item_desc = f"{o['stars_amount']}⭐" if o["kind"] == "stars" else o["item_title"]
        lines.append(
            f"#{o['order_id']} | @{o['username'] or '—'} | {item_desc} | "
            f"${o['price_usd']:.2f} | {o['currency']} | {o['status']}"
        )
    await call.message.edit_text("\n".join(lines), reply_markup=kb.admin_menu_kb())
    await call.answer()


@router.callback_query(F.data == "a_settings")
async def a_settings(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"Базовая цена/звезда: ${cfg.base_price_per_star_usd}\n"
        f"Курс TON/USD: {cfg.ton_usd_rate}\n"
        f"Курс TRX/USD: {cfg.trx_usd_rate}\n"
        f"Мин/Макс заказ: {cfg.min_stars} / {cfg.max_stars}\n\n"
        "Изменение курсов и тарифов — через .env / config.py "
        "(в этой версии — редактирование значений напрямую в конфиге; "
        "по запросу можно добавить редактирование прямо из чата)."
    )
    await call.message.edit_text(text, reply_markup=kb.admin_menu_kb())
    await call.answer()


def _format_order_notification(order, extra_line: str | None = None) -> str:
    """
    Единая функция форматирования карточки заказа для админа. Используется
    и для исходного уведомления, и при пометке заказа выданным/отменённым —
    так HTML-форматирование не теряется.

    Раньше при "Отметить выданным"/"Отменить заказ" код брал
    call.message.text и просто дописывал строку. Telegram отдаёт .text
    уже БЕЗ HTML-тегов (форматирование хранится отдельно как "entities"),
    поэтому такая склейка на редактировании стирала весь жирный текст
    и структуру сообщения. Теперь сообщение всегда собирается заново.
    """
    text = (
        "🆕 <b>Заказ</b>\n\n"
        f"👤 Пользователь: @{order['username'] or '—'} (ID: <code>{order['user_id']}</code>)\n"
        f"⭐ Количество Stars: <b>{order['stars_amount']}</b>\n"
        f"💵 Сумма: <b>${order['price_usd']:.2f}</b>\n"
        f"💳 Способ оплаты: <b>{order['currency']}</b>\n"
        f"🆔 ID заказа: <code>{order['order_id']}</code>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
    )
    if extra_line:
        text += f"\n{extra_line}"
    return text


async def notify_admin_new_order(bot: Bot, order):
    """Отправляет админу уведомление о новом (оплаченном) заказе."""
    await bot.send_message(
        cfg.admin_id,
        _format_order_notification(order),
        reply_markup=kb.admin_order_actions_kb(order["order_id"]),
    )


@router.callback_query(F.data.startswith("a_deliver:"))
async def a_deliver(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return await call.answer()
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if order["status"] not in ("paid",):
        await call.answer(f"Нельзя выдать заказ в статусе «{order['status']}».", show_alert=True)
        return

    await db.set_order_status(order_id, "delivered")
    order = await db.get_order(order_id)  # перечитываем актуальный статус
    await call.message.edit_text(
        _format_order_notification(order, "✅ Отмечено как выдано."),
        reply_markup=None,
    )
    await call.answer("Готово")
    try:
        await bot.send_message(
            order["user_id"],
            f"🎉 Ваш заказ #{order_id} на {order['stars_amount']}⭐ выполнен! Спасибо за покупку.",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("a_cancel:"))
async def a_cancel(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return await call.answer()
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if order["status"] in ("cancelled", "delivered"):
        await call.answer(f"Заказ уже в статусе «{order['status']}».", show_alert=True)
        return

    await db.set_order_status(order_id, "cancelled")
    order = await db.get_order(order_id)
    await call.message.edit_text(
        _format_order_notification(order, "❌ Заказ отменён администратором."),
        reply_markup=None,
    )
    await call.answer("Отменено")
    try:
        await bot.send_message(
            order["user_id"],
            f"⚠️ Ваш заказ #{order_id} был отменён администратором. "
            f"Свяжитесь с поддержкой: @{cfg.support_username}",
        )
    except Exception:
        pass


# ---------- Заказы на доп.товары (подарки / Premium) ----------

def _format_extra_order_notification(order, extra_line: str | None = None) -> str:
    kind_label = "🎁 Подарок" if order["kind"] == "gift" else "🔥 Telegram Premium"
    text = (
        f"🆕 <b>Новый заказ ({kind_label})</b>\n\n"
        f"👤 Пользователь: @{order['username'] or '—'} (ID: <code>{order['user_id']}</code>)\n"
        f"🎯 Товар: <b>{order['item_title']}</b>\n"
        f"💵 Сумма: <b>${order['price_usd']:.2f}</b>\n"
        f"💳 Способ оплаты: <b>{order['currency']}</b>\n"
        f"🆔 ID заказа: <code>{order['order_id']}</code>\n"
        f"📌 Статус: <b>{order['status']}</b>\n"
    )
    if extra_line:
        text += f"\n{extra_line}"
    return text


async def notify_admin_extra_order(bot: Bot, order):
    """Отправляет админу уведомление о новом (оплаченном) заказе подарка/Premium."""
    await bot.send_message(
        cfg.admin_id,
        _format_extra_order_notification(order),
        reply_markup=kb.admin_extra_order_actions_kb(order["order_id"]),
    )


@router.callback_query(F.data.startswith("a_edeliver:"))
async def a_extra_deliver(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return await call.answer()
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if order["status"] != "paid":
        await call.answer(f"Нельзя выдать заказ в статусе «{order['status']}».", show_alert=True)
        return

    await db.set_order_status(order_id, "delivered")
    order = await db.get_order(order_id)
    await call.message.edit_text(
        _format_extra_order_notification(order, "✅ Отмечено как выдано."),
        reply_markup=None,
    )
    await call.answer("Готово")
    try:
        await bot.send_message(
            order["user_id"],
            f"🎉 Ваш заказ #{order_id} («{order['item_title']}») выполнен! Спасибо за покупку.",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("a_ecancel:"))
async def a_extra_cancel(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return await call.answer()
    order_id = call.data.split(":", 1)[1]
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    if order["status"] in ("cancelled", "delivered"):
        await call.answer(f"Заказ уже в статусе «{order['status']}».", show_alert=True)
        return

    await db.set_order_status(order_id, "cancelled")
    order = await db.get_order(order_id)
    await call.message.edit_text(
        _format_extra_order_notification(order, "❌ Заказ отменён администратором."),
        reply_markup=None,
    )
    await call.answer("Отменено")
    try:
        await bot.send_message(
            order["user_id"],
            f"⚠️ Ваш заказ #{order_id} был отменён администратором. "
            f"Свяжитесь с поддержкой: @{cfg.support_username}",
        )
    except Exception:
        pass
