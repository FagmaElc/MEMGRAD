import asyncio
import logging
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from handlers import register_handlers

from aiohttp import web

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Проверка переменных
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment!")

# Глобальные объекты
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# 📌 AIOHTTP-сервер
async def handle_ping(request):
    return web.Response(text="I'm alive!")

def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/ping", handle_ping)
    return app


async def run():
    logging.basicConfig(level=logging.INFO)

    # Регистрируем хендлеры
    register_handlers(dp)

    # Запускаем aiohttp сервер
    runner = web.AppRunner(create_web_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 5000)))
    await site.start()
    logging.info("Web server started on port 5000")

    # Запускаем бота в polling режиме
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")