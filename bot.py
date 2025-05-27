import sqlite3
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = "8018881136:AAFoH6PXITrIbj45PfftBlx-fSWepZ3fdmg"
ADMIN_ID = 1236771535

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, number TEXT, active INTEGER DEFAULT 1, usage_count INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service TEXT, amount INTEGER, exact_amount INTEGER, xbet_id TEXT, card TEXT, status TEXT, created_at TEXT, file_id TEXT)")
conn.commit()

user_states = {}

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("📩 Пополнение", "📤 Вывод")

def get_card():
    cursor.execute("SELECT id, number FROM cards WHERE active = 1 ORDER BY usage_count ASC LIMIT 1")
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE cards SET usage_count = usage_count + 1 WHERE id = ?", (row[0],))
        conn.commit()
        return row[1]
    return None

@dp.message_handler(commands=["start"])
async def start_cmd(msg: types.Message):
    await msg.answer("Выберите действие:", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == "📩 Пополнение")
async def handle_topup(msg: types.Message):
    user_states[msg.from_user.id] = {"step": "card", "service": "Пополнение"}
    await msg.answer("Введите номер вашей карты (отправитель):")

@dp.message_handler(lambda m: m.text == "📤 Вывод")
async def handle_withdraw(msg: types.Message):
    user_states[msg.from_user.id] = {"step": "card", "service": "Вывод"}
    await msg.answer("Введите номер вашей карты (получатель):")

@dp.message_handler()
async def handle_input(msg: types.Message):
    state = user_states.get(msg.from_user.id)
    if not state:
        return

    step = state["step"]
    if step == "card":
        state["card"] = msg.text.strip()
        state["step"] = "xbet"
        await msg.answer("Введите ID 1xBet:")
    elif step == "xbet":
        state["xbet_id"] = msg.text.strip()
        state["step"] = "amount"
        await msg.answer("Введите сумму (от 30000 до 30000000):")
    elif step == "amount":
        try:
            amount = int(msg.text.strip())
            if amount < 30000 or amount > 30000000:
                await msg.answer("Недопустимая сумма.")
                return
            exact = amount + random.randint(1, 9)
            card = get_card() if state["service"] == "Пополнение" else state["card"]
            if not card:
                await msg.answer("Нет доступных карт. Обратитесь в поддержку.")
                return
            state["amount"] = amount
            state["exact"] = exact
            state["card_used"] = card
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO requests (user_id, service, amount, exact_amount, xbet_id, card, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'ожидает', ?)",
                (msg.from_user.id, state["service"], amount, exact, state["xbet_id"], card, created_at))
            conn.commit()
            req_id = cursor.lastrowid
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{req_id}")
            )
            await msg.answer(
                f"Переведите <b>{exact} сум</b> на карту:
<code>{card}</code>

"
                f"Нельзя: {amount} сум ❌
Нужно: {exact} сум ✅

"
                f"После перевода нажмите «Я оплатил» в течение 15 минут.",
                parse_mode="HTML", reply_markup=kb)
            user_states.pop(msg.from_user.id)
        except:
            await msg.answer("Введите корректную сумму.")

@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def handle_paid(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET status = 'на проверке' WHERE id = ?", (rid,))
    conn.commit()
    await callback.message.answer("Отправьте чек (фото или PDF).")
    await callback.answer()

@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT])
async def handle_upload(msg: types.Message):
    cursor.execute("SELECT id FROM requests WHERE user_id = ? AND status = 'на проверке' ORDER BY id DESC LIMIT 1", (msg.from_user.id,))
    row = cursor.fetchone()
    if not row:
        return
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    cursor.execute("UPDATE requests SET file_id = ?, status = 'ожидает' WHERE id = ?", (file_id, row[0]))
    conn.commit()
    await msg.answer("Чек сохранён. Ожидайте подтверждение.")

@dp.message_handler(commands=["addcard"])
async def add_card(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    parts = msg.text.split()
    if len(parts) != 2:
        await msg.answer("Формат: /addcard 9860XXXX...")
        return
    cursor.execute("INSERT INTO cards (number) VALUES (?)", (parts[1],))
    conn.commit()
    await msg.answer("Карта добавлена.")

@dp.message_handler(commands=["cards"])
async def show_cards(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT id, number, usage_count FROM cards WHERE active = 1")
    rows = cursor.fetchall()
    if not rows:
        await msg.answer("Нет активных карт.")
        return
    text = "\n".join([f"{r[0]}: {r[1]} — {r[2]} раз" for r in rows])
    await msg.answer(text)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
