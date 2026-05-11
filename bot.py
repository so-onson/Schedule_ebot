import asyncio
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher

from handlers import router
from db import init_db

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scheduler import check_sessions


load_dotenv()

TOKEN = os.getenv("TOKEN")


async def main():

    init_db()

    bot = Bot(token=TOKEN)

    dp = Dispatcher()

    dp.include_router(router)

    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        check_sessions,
        "interval",
        minutes=10,
        args=[bot]
    )

    scheduler.start()

    print("Бот запущен")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())