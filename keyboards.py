from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import cfg

QUICK_AMOUNTS = [50, 100, 250, 500, 1000, 5000]


def main_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⭐ Купить Stars", callback_data="buy")
    b.button(text="📦 Мои заказы", callback_data="my_orders")
    b.button(text="💬 Поддержка", url=f"https://t.me/{cfg.support_username}")
    b.adjust(1)
    return b.as_markup()


def amounts_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for amt in QUICK_AMOUNTS:
        b.button(text=f"{amt} ⭐", callback_data=f"amt:{amt}")
    b.button(text="✏️ Своё количество", callback_data="amt:custom")
    b.button(text="⬅️ Назад", callback_data="back_main")
    b.adjust(3, 3, 1, 1)
    return b.as_markup()


def confirm_amount_kb(stars: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💎 Оплатить TON", callback_data=f"pay:TON:{stars}")
    b.button(text="🔺 Оплатить TRX", callback_data=f"pay:TRX:{stars}")
    b.button(text="⬅️ Назад", callback_data="buy")
    b.adjust(1)
    return b.as_markup()


def order_check_kb(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Проверить оплату", callback_data=f"check:{order_id}")
    b.button(text="❌ Отменить заказ", callback_data=f"cancel:{order_id}")
    b.button(text="💬 Поддержка", url=f"https://t.me/{cfg.support_username}")
    b.adjust(1)
    return b.as_markup()


def back_kb(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data=callback_data)
    return b.as_markup()


# ---------- Admin ----------

def admin_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика", callback_data="a_stats")
    b.button(text="📋 Последние заказы", callback_data="a_orders")
    b.button(text="⚙️ Настройки", callback_data="a_settings")
    b.adjust(1)
    return b.as_markup()


def admin_order_actions_kb(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отметить выданным", callback_data=f"a_deliver:{order_id}")
    b.button(text="❌ Отменить заказ", callback_data=f"a_cancel:{order_id}")
    b.adjust(1)
    return b.as_markup()
