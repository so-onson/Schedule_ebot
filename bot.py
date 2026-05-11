import asyncio
from aiogram import Bot, Dispatcher
from config import TOKEN
from handlers import router
from db import init_db

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scheduler import check_sessions

async def main():
    init_db()

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    print("Бот запущен")
    await dp.start_polling(bot)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_sessions, "interval", minutes=10, args=[bot])
    scheduler.start()

if __name__ == "__main__":
    asyncio.run(main())