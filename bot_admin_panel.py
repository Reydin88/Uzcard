
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, os
from datetime import datetime

BOT_TOKEN = "8077158709:AAEvzGF3H4Ey1V597aHJcylpWirI0eXyGlQ"
ADMIN_IDS = [1236771535]
DB = "db.sqlite3"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
conn = sqlite3.connect(DB, check_same_thread=False)
cursor = conn.cursor()

@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Пополнение 1xBet", callback_data="svc_topup"),
        InlineKeyboardButton("Вывод с 1xBet", callback_data="svc_withdraw")
    )
    await msg.answer("Выберите услугу:", reply_markup=kb)

@dp.message_handler(commands=["admin"])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("Нет доступа.")
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Заявки", callback_data="admin_requests"),
        InlineKeyboardButton("Карты", callback_data="admin_cards"),
        InlineKeyboardButton("Excel", callback_data="admin_excel")
    )
    await message.answer("Админ-панель", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "admin_requests")
async def view_requests(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    cursor.execute("SELECT id, service, amount, xbet_id, status FROM requests ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        return await callback.message.edit_text("Нет заявок.")
    text = "\n".join([f"#{r[0]} | {r[1]} | {r[2]} сум | ID: {r[3]} | Статус: {r[4]}" for r in rows])
    await callback.message.edit_text("Последние заявки:\n\n" + text)

@dp.callback_query_handler(lambda c: c.data == "admin_cards")
async def view_cards(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    cursor.execute("SELECT id, number, active, usage_count FROM cards ORDER BY id")
    cards = cursor.fetchall()
    if not cards:
        return await callback.message.edit_text("Карт нет.")
    text = "\n".join([f"{'✅' if c[2] else '❌'} {c[1]} (исп: {c[3]}) — /togglecard_{c[0]}" for c in cards])
    await callback.message.edit_text("Карты:\n" + text + "\n\nЧтобы переключить: /togglecard_ID")

@dp.message_handler(lambda m: m.text.startswith("/togglecard_"))
async def toggle_card(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        cid = int(message.text.split("_")[1])
        cursor.execute("UPDATE cards SET active = 1 - active WHERE id = ?", (cid,))
        conn.commit()
        await message.reply(f"Карта #{cid} переключена.")
    except:
        await message.reply("Ошибка.")

@dp.callback_query_handler(lambda c: c.data == "admin_excel")
async def send_excel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    import pandas as pd
    df = pd.read_sql_query("SELECT * FROM requests", conn)
    path = "requests_export.xlsx"
    df.to_excel(path, index=False)
    await bot.send_document(callback.from_user.id, open(path, "rb"))


@dp.message_handler(commands=["addcard"])
async def add_card(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("Нет доступа.")
    args = message.text.split()
    if len(args) != 2:
        return await message.reply("Используй формат:\n/addcard 9860XXXXXXXXXXXX")
    number = args[1]
    cursor.execute("INSERT INTO cards (number) VALUES (?)", (number,))
    conn.commit()
    await message.reply(f"Карта {number} добавлена.")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
