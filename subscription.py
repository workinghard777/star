"""
Гейт обязательной подписки на канал перед использованием бота.
Подключается как middleware поверх существующих роутеров в main.py —
хендлеры user.py/admin.py не меняются.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import cfg

REQUIRED_CHANNEL = "@ww_vouch"
REQUIRED_CHANNEL_URL = "https://t.me/ww_vouch"

GATE_TEXT = (
    "Чтобы перейти далее, пожалуйста, подпишитесь на наш информационный канал\n"
    "👇"
)


def gate_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔗 Перейти в канал", url=REQUIRED_CHANNEL_URL)
    b.button(text="✅ Проверить подписку", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()


async def is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status not in ("left", "kicked")
    except TelegramBadRequest:
        # Если бот не админ канала или канал недоступен — не блокируем всех
        # пользователей из-за ошибки конфигурации.
        return True


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        if user.id == cfg.admin_id:
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)

        bot = data["bot"]
        if await is_subscribed(bot, user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.answer(GATE_TEXT, reply_markup=gate_kb())
            return
        if isinstance(event, Message):
            await event.answer(GATE_TEXT, reply_markup=gate_kb())
            return


router = Router()


@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    if await is_subscribed(call.bot, call.from_user.id):
        from handlers.user import WELCOME_TEXT
        import keyboards as kb
        await call.message.edit_text(WELCOME_TEXT, reply_markup=kb.main_menu_kb())
        await call.answer()
    else:
        await call.answer("Вы всё ещё не подписаны 🙁", show_alert=True)
