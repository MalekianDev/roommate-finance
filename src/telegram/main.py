import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from settings import Settings
from telegram.middlewares.db import DBSessionMiddleware
from telegram.handlers import start_router

settings = Settings()
dispatcher = Dispatcher()
dispatcher.update.middleware(DBSessionMiddleware())

dispatcher.include_router(start_router)


async def main() -> None:
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
