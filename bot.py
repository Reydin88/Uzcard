
from aiogram import Bot, Dispatcher, types, executor
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.reply("Добро пожаловать в uzcardsbot!")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
