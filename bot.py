from aiogram import Bot, Dispatcher, types, executor

BOT_TOKEN = "7886334338:AAEh6rFvpaSngbrSk94aRHdC-jmpWlJB6Bk"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("Привет! uzcardsbot работает!")

if __name__ == "__main__":
    print("✅ Бот запущен. Ожидание сообщений...")
    executor.start_polling(dp, skip_updates=True)
