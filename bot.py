
import os, sqlite3, asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8018881136:AAFoH6PXITrIbj45PfftBlx-fSWepZ3fdmg"
ADMIN_IDS = [1236771535]
DB = "db.sqlite3"
LIMITS = {"topup": (10000, 5000000), "withdraw": (50000, 3000000)}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
conn = sqlite3.connect(DB, check_same_thread=False)
cursor = conn.cursor()

cursor.executescript("""
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
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    paid_at TEXT,
    file1 TEXT,
    file2 TEXT
);
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    blocked INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT,
    active INTEGER DEFAULT 1,
    usage_count INTEGER DEFAULT 0
);
""")
conn.commit()
user_data = {}

@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    user_id = msg.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] == 1:
        return await msg.answer("Вы заблокированы.")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Пополнение 1xBet", callback_data="svc_topup"),
        InlineKeyboardButton("Вывод с 1xBet", callback_data="svc_withdraw")
    )
    await msg.answer("Выберите услугу:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("svc_"))
async def choose_service(callback: types.CallbackQuery):
    service = callback.data.split("_")[1]
    user_data[callback.from_user.id] = {"service": service, "step": "amount"}
    await callback.message.edit_text("Введите сумму:")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "amount")
async def input_amount(message: types.Message):
    uid = message.from_user.id
    try:
        amt = int(message.text.strip())
    except:
        return await message.reply("Введите число.")
    service = user_data[uid]["service"]
    min_limit, max_limit = LIMITS[service]
    if not (min_limit <= amt <= max_limit):
        return await message.reply(f"Сумма должна быть от {min_limit} до {max_limit} сум.")
    user_data[uid]["amount"] = amt
    user_data[uid]["step"] = "xbet_id"
    await message.answer("Введите ваш ID 1xBet:")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "xbet_id")
async def input_xbet_id(message: types.Message):
    user_data[message.from_user.id]["xbet_id"] = message.text.strip()
    if user_data[message.from_user.id]["service"] == "topup":
        user_data[message.from_user.id]["step"] = "sender_card"
        await message.answer("Введите номер вашей карты (отправителя):")
    else:
        user_data[message.from_user.id]["step"] = "recv_fio"
        await message.answer("Введите ФИО получателя:")

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get("step") == "sender_card")
async def input_sender_card(message: types.Message):
    uid = message.from_user.id
    user_data[uid]["sender_card"] = message.text.strip()
    data = user_data.pop(uid)
    card_to_pay = "9860 6004 0948 1908"
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO requests (user_id, service, amount, xbet_id, sender_card, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, "topup", data["amount"], data["xbet_id"], data["sender_card"], now)
    )
    conn.commit()
    req_id = cursor.lastrowid
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{req_id}"))
    text = (
        f"Переведите {data['amount']} сум на карту:"
        f"`{card_to_pay}`"
        "После перевода нажмите кнопку ниже."
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"📥 Заявка #{req_id} (пополнение): {data['amount']} сум от {data['sender_card']}")

@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def confirm_paid(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET paid_at=? WHERE id=?", (datetime.now().isoformat(), req_id))
    conn.commit()
    await callback.message.answer("Пожалуйста, отправьте чек (фото или PDF).")

@dp.message_handler(content_types=[types.ContentType.DOCUMENT, types.ContentType.PHOTO])
async def receive_file(message: types.Message):
    uid = message.from_user.id
    cursor.execute("SELECT id FROM requests WHERE user_id=? AND status='ожидает' ORDER BY id DESC LIMIT 1", (uid,))
    row = cursor.fetchone()
    if not row:
        return await message.answer("Нет активной заявки.")
    req_id = row[0]
    f = message.document or message.photo[-1]
    os.makedirs("checks", exist_ok=True)
    path = f"checks/{req_id}_{datetime.now().timestamp()}.jpg" if message.photo else f"checks/{f.file_name}"
    await f.download(destination_file=path)
    cursor.execute("SELECT file1, file2 FROM requests WHERE id=?", (req_id,))
    f1, f2 = cursor.fetchone()
    if not f1:
        cursor.execute("UPDATE requests SET file1=? WHERE id=?", (path, req_id))
    elif not f2:
        cursor.execute("UPDATE requests SET file2=? WHERE id=?", (path, req_id))
    else:
        return await message.answer("Можно загрузить не более 2-х файлов.")
    conn.commit()
    await message.answer("Чек получен. Оператор скоро проверит заявку.")
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"Поступил чек для заявки #{req_id}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
