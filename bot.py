
from aiogram import Bot, Dispatcher, types, executor

BOT_TOKEN = "7886334338:AAEh6rFvpaSngbrSk94aRHdC-jmpWlJB6Bk"
ADMIN_IDS = [1236771535]  # список админов

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("Привет, админ! uzcardsbot полностью работает!")
    else:
        await message.answer("Привет! Добро пожаловать в uzcardsbot.")

if __name__ == "__main__":
    print("✅ Бот запущен. Ожидание сообщений...")
    executor.start_polling(dp, skip_updates=True)
