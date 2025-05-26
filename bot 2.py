
from aiogram import Bot, Dispatcher, types, executor
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не указан!")
    exit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("Привет! uzcardsbot работает!")

if __name__ == "__main__":
    print("✅ Бот запущен. Ожидание сообщений...")
    executor.start_polling(dp, skip_updates=True)
