import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    # Тут позже подключим хендлеры
    print("Бот запущен (пока без логики).")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
