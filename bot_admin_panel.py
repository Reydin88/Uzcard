from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, logging, random
from datetime import datetime

API_TOKEN = "7878879986:AAEnUlGIKo6MYyzsqny20qnX9adlITGF--s"
ADMIN_IDS = [1236771535]
MIN_AMOUNT = 30000
MAX_AMOUNT = 30000000

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS cards (id INTEGER PRIMARY KEY, number TEXT, active INTEGER DEFAULT 1, usage_count INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service TEXT, amount INTEGER, exact_amount INTEGER, xbet_id TEXT, card TEXT, status TEXT, created_at TEXT, file_id TEXT)")
conn.commit()

user_states = {}

# Reply-кнопки
menu_kb = ReplyKeyboardMarkup(resize_keyboard=True)
menu_kb.add("📩 Пополнить баланс", "📤 Вывести средства")
menu_kb.add("📈 Курс", "🧾 История")
menu_kb.add("👨‍💻 Связь с поддержкой")

@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    user_states.pop(message.from_user.id, None)
    await message.answer("Добро пожаловать в UZpay!
Главное меню, что будем делать?", reply_markup=menu_kb)

@dp.message_handler(lambda m: m.text == "📩 Пополнить баланс")
async def topup_start(message: types.Message):
    user_states[message.from_user.id] = {"step": "enter_card", "service": "Пополнение"}
    await message.answer("Введите номер карты:")

@dp.message_handler(lambda m: m.text == "📤 Вывести средства")
async def withdraw_start(message: types.Message):
    user_states[message.from_user.id] = {"step": "enter_card", "service": "Вывод"}
    await message.answer("Введите номер карты получателя:")

@dp.message_handler()
async def process_steps(message: types.Message):
    state = user_states.get(message.from_user.id)
    if not state:
        return

    if state["step"] == "enter_card":
        state["card"] = message.text.strip()
        state["step"] = "enter_xbet"
        await message.answer("Введите номер счёта (ID 1xBet):")

    elif state["step"] == "enter_xbet":
        state["xbet_id"] = message.text.strip()
        state["step"] = "enter_amount"
        await message.answer(f"Минимум: {MIN_AMOUNT} UZS
Максимум: {MAX_AMOUNT} UZS

Введите сумму:")

    elif state["step"] == "enter_amount":
        try:
            amount = int(message.text.strip())
            if not (MIN_AMOUNT <= amount <= MAX_AMOUNT):
                return await message.answer("Сумма вне допустимого диапазона.")
            exact = amount + random.randint(1, 9)
            card = get_active_card()
            tg_id = message.from_user.id
            state.update({"amount": amount, "exact": exact, "card_used": card})
            cursor.execute("INSERT INTO requests (user_id, service, amount, exact_amount, xbet_id, card, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'ожидает', ?)",
                (tg_id, state["service"], amount, exact, state["xbet_id"], card, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            req_id = cursor.lastrowid

            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{req_id}"),
                InlineKeyboardButton("🚫 Отменить", callback_data=f"cancel_{req_id}")
            )

            await message.answer(
                f"<b>Внимание!</b> Переведите точную <b>{exact} UZS</b>, она отличается от вашей суммы!

"
                f"Карта для перевода: <code>{card}</code>
"
                f"НЕ ПЕРЕВОДИТЬ: {amount} UZS ❌
"
                f"НУЖНО перевести: <b>{exact} UZS</b> ✅

"
                f"✅ После внесения средств, нажмите кнопку «Подтвердить» в течение 5 минут!
"
                f"⛔ Если ошиблись и другую сумму перевели — мы вернём деньги в течение 15 раб. дней!

"
                f"TG_ID: {tg_id} #{req_id}",
                parse_mode="HTML", reply_markup=kb)
            user_states.pop(message.from_user.id)

        except:
            await message.answer("Введите корректную сумму.")

@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def confirm_payment(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET status = 'на проверке' WHERE id = ?", (rid,))
    conn.commit()
    await callback.message.answer("Чек получен. Ожидайте подтверждение.")
    await callback.answer()

@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT])
async def receive_check(message: types.Message):
    cursor.execute("SELECT id FROM requests WHERE user_id = ? AND status = 'на проверке' ORDER BY id DESC LIMIT 1", (message.from_user.id,))
    row = cursor.fetchone()
    if not row:
        return
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    cursor.execute("UPDATE requests SET file_id = ? WHERE id = ?", (file_id, row[0]))
    conn.commit()
    await message.reply("Чек сохранён. Заявка передана оператору.")

@dp.message_handler(commands=["addcard"])
async def add_card(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        num = message.text.split()[1]
        cursor.execute("INSERT INTO cards (number) VALUES (?)", (num,))
        conn.commit()
        await message.answer("Карта добавлена.")
    except:
        await message.answer("Ошибка. Используй: /addcard 9860...")

@dp.message_handler(commands=["cards"])
async def list_cards(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    cursor.execute("SELECT id, number, usage_count FROM cards WHERE active = 1")
    rows = cursor.fetchall()
    if not rows:
        return await message.answer("Нет активных карт.")
    msg = "\n".join([f"{r[0]}: {r[1]} (использована {r[2]} раз)" for r in rows])
    await message.answer(msg)

def get_active_card():
    cursor.execute("SELECT id, number FROM cards WHERE active = 1 ORDER BY usage_count ASC LIMIT 1")
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE cards SET usage_count = usage_count + 1 WHERE id = ?", (row[0],))
        conn.commit()
        return row[1]
    return "9860 0000 0000 0000"

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)