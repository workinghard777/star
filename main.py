import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import cfg
import database as db
from handlers import user, admin, gifts, premium
from payments.checker import payment_polling_loop
from payments.checker_extra import extra_payment_polling_loop
from subscription import SubscriptionMiddleware
import subscription

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("main")


async def main():
    if not cfg.bot_token:
        raise RuntimeError("BOT_TOKEN не задан. Заполните .env на основе .env.example")

    await db.init_db()

    bot = Bot(token=cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Гейт обязательной подписки на канал — проверяется раньше всех остальных хендлеров
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    dp.include_router(admin.router)  # admin раньше user, чтобы скрытая команда не пересекалась
    dp.include_router(subscription.router)
    dp.include_router(gifts.router)
    dp.include_router(premium.router)
    dp.include_router(user.router)

    # Фоновые задачи проверки платежей
    asyncio.create_task(payment_polling_loop(bot))
    asyncio.create_task(extra_payment_polling_loop(bot))

    log.info("Star Market bot started")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
