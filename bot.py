import os
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from datetime import datetime

BOT_TOKEN = "8077158709:AAH44z1eWfUfP1oT3GqMZ0ouILzEP9rzcJ4"
ADMIN_IDS = [1236771535]
DB = "db.sqlite3"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect(DB, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    service TEXT,
    amount INTEGER,
    xbet_id TEXT,
    sender_card TEXT,
    recv_fio TEXT,
    recv_card TEXT,
    confirm_code TEXT,
    status TEXT DEFAULT 'ожидает',
    paid_confirmed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

user_data = {}

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("Пополнение 1xBet", callback_data="topup"),
        types.InlineKeyboardButton("Вывод с 1xBet", callback_data="withdraw")
    )
    await message.answer("Выберите услугу:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data in ["topup", "withdraw"])
async def service_choose(callback: types.CallbackQuery):
    user_data[callback.from_user.id] = {"service": callback.data, "step": "amount"}
    await callback.message.answer("Введите сумму (в сумах):")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "amount")
async def step_amount(message: types.Message):
    try:
        amount = int(message.text.strip())
        user_data[message.from_user.id]["amount"] = amount
        user_data[message.from_user.id]["step"] = "xbet_id"
        await message.answer("Введите ID 1xBet:")
    except:
        await message.answer("Введите число.")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "xbet_id")
async def step_xbet(message: types.Message):
    user_data[message.from_user.id]["xbet_id"] = message.text.strip()
    if user_data[message.from_user.id]["service"] == "topup":
        user_data[message.from_user.id]["step"] = "sender_card"
        await message.answer("Введите номер вашей карты (отправителя):")
    else:
        user_data[message.from_user.id]["step"] = "recv_fio"
        await message.answer("Введите ФИО получателя:")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "sender_card")
async def step_sender_card(message: types.Message):
    user_data[message.from_user.id]["sender_card"] = message.text.strip()
    data = user_data.pop(message.from_user.id)
    cursor.execute("""
        INSERT INTO requests (user_id, service, amount, xbet_id, sender_card)
        VALUES (?, ?, ?, ?, ?)
    """, (message.from_user.id, "topup", data["amount"], data["xbet_id"], data["sender_card"]))
    conn.commit()
    req_id = cursor.lastrowid

    # Отправка админу
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"Заявка #{req_id} (Пополнение)\nСумма: {data['amount']}\nID: {data['xbet_id']}\nКарта: {data['sender_card']}")
    await message.answer("✅ Ваша заявка отправлена оператору. Ожидайте подтверждение.")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "recv_fio")
async def step_fio(message: types.Message):
    user_data[message.from_user.id]["recv_fio"] = message.text.strip()
    user_data[message.from_user.id]["step"] = "recv_card"
    await message.answer("Введите номер карты получателя:")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "recv_card")
async def step_recv_card(message: types.Message):
    user_data[message.from_user.id]["recv_card"] = message.text.strip()
    user_data[message.from_user.id]["step"] = "confirm_code"
    await message.answer("Введите код подтверждения от 1xBet:")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "confirm_code")
async def step_code(message: types.Message):
    data = user_data.pop(message.from_user.id)
    data["confirm_code"] = message.text.strip()
    cursor.execute("""
        INSERT INTO requests (user_id, service, amount, xbet_id, recv_fio, recv_card, confirm_code)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (message.from_user.id, "withdraw", data["amount"], data["xbet_id"], data["recv_fio"], data["recv_card"], data["confirm_code"]))
    conn.commit()
    req_id = cursor.lastrowid

    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"Заявка #{req_id} (Вывод)\nСумма: {data['amount']}\nID: {data['xbet_id']}\nФИО: {data['recv_fio']}\nКарта: {data['recv_card']}\nКод: {data['confirm_code']}")
    await message.answer("✅ Заявка отправлена. Ожидайте.")
    
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
