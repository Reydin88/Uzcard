from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
import sqlite3, os
from datetime import datetime

BOT_TOKEN = "7878879986:AAEnUlGIKo6MYyzsqny20qnX9adlITGF--s"
ADMIN_IDS = [1236771535]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cursor = conn.cursor()

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("Пополнение", "Вывод")

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Выберите действие:", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == "Пополнение")
async def start_topup(msg: types.Message):
    await msg.answer("Введите сумму:")
    dp.register_message_handler(lambda m: ask_id(m, int(m.text)), state="ask_amount")

async def ask_id(msg: types.Message, amount):
    await msg.answer("Введите ваш ID 1xBet:")
    dp.register_message_handler(lambda m: confirm_topup(m, amount, m.text), state="ask_id")

def get_active_card():
    cursor.execute("SELECT id, number FROM cards WHERE active = 1 ORDER BY usage_count ASC LIMIT 1")
    card = cursor.fetchone()
    if card:
        cursor.execute("UPDATE cards SET usage_count = usage_count + 1 WHERE id = ?", (card[0],))
        conn.commit()
        return card[1]
    return "9860 0000 0000 0000"

async def confirm_topup(msg: types.Message, amount, xbet_id):
    card = get_active_card()
    cursor.execute("INSERT INTO requests (user_id, service, amount, xbet_id, status, created_at) VALUES (?, 'Пополнение', ?, ?, 'ожидает', ?)", 
        (msg.from_user.id, amount, xbet_id.strip(), datetime.now()))
    conn.commit()
    req_id = cursor.lastrowid
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{req_id}"))
    await msg.answer(
        f"Переведите {amount} сум на карту:

<code>{card}</code>

"
        f"Затем нажмите кнопку ниже.", parse_mode="HTML", reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def paid_check(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET status = 'на проверке' WHERE id = ?", (rid,))
    conn.commit()
    await callback.message.answer("Теперь отправьте фото или PDF чека.")
    await callback.answer()

@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT])
async def receive_file(msg: types.Message):
    cursor.execute("SELECT id FROM requests WHERE user_id = ? AND status = 'на проверке' ORDER BY id DESC LIMIT 1", (msg.from_user.id,))
    row = cursor.fetchone()
    if not row:
        return await msg.reply("Нет ожидающей заявки.")
    fid = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    cursor.execute("UPDATE requests SET file1 = ? WHERE id = ?", (fid, row[0]))
    conn.commit()
    await msg.reply("Чек получен. Ожидайте подтверждение.")

@dp.message_handler(commands=["admin"])
async def admin_panel(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    cursor.execute("SELECT id, amount, xbet_id, status FROM requests ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    for r in rows:
        rid, amount, xid, status = r
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"ok_{rid}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{rid}")
        )
        await msg.answer(f"#{rid} | {amount} сум | ID {xid} | Статус: {status}", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
async def decision(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    status = "подтверждено" if callback.data.startswith("ok_") else "отклонено"
    cursor.execute("UPDATE requests SET status = ? WHERE id = ?", (status, rid))
    conn.commit()
    await callback.message.edit_text(f"Заявка #{rid} {status}")
    await callback.answer()

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)