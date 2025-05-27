import os
import sqlite3
import random
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton

# ——— Настройки ———
API_TOKEN = "7878879986:AAEnUlGIKo6MYyzsqny20qnX9adlITGF--s"
ADMIN_IDS = [1236771535]
MIN_AMOUNT = 30000
MAX_AMOUNT = 30000000

# ——— Инициализация ———
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cursor = conn.cursor()
# Автоматически создаём таблицы, если их нет
cursor.execute("""
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    usage_count INTEGER NOT NULL DEFAULT 0
);
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    service TEXT NOT NULL,
    amount INTEGER NOT NULL,
    exact_amount INTEGER,
    xbet_id TEXT,
    card TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    file_id TEXT
);
""")
conn.commit()

user_states = {}  # хранит { user_id: {"service": "...", "step": "...", ...} }

# ——— Глобальные клавиатуры ———
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("📩 Пополнить баланс", "📤 Вывести средства")
main_kb.add("🧾 Мои заявки", "👤 Профиль")


def get_active_card() -> str:
    """Берёт самую малоиспользуемую активную карту."""
    cursor.execute(
        "SELECT id, number FROM cards WHERE active=1 ORDER BY usage_count ASC LIMIT 1"
    )
    row = cursor.fetchone()
    if row:
        cid, number = row
        cursor.execute(
            "UPDATE cards SET usage_count = usage_count + 1 WHERE id = ?", (cid,)
        )
        conn.commit()
        return number
    return None


@dp.message_handler(commands=["start"])
async def cmd_start(msg: types.Message):
    user_states.pop(msg.from_user.id, None)
    await msg.answer(
        "Добро пожаловать! Выберите действие:",
        reply_markup=main_kb
    )


@dp.message_handler(lambda m: m.text == "📩 Пополнить баланс")
async def start_topup(msg: types.Message):
    user_states[msg.from_user.id] = {"service": "Пополнение", "step": "card"}
    await msg.answer("Введите номер вашей карты (отправитель):")


@dp.message_handler(lambda m: m.text == "📤 Вывести средства")
async def start_withdraw(msg: types.Message):
    user_states[msg.from_user.id] = {"service": "Вывод", "step": "card"}
    await msg.answer("Введите номер вашей карты (получатель):")


@dp.message_handler(lambda m: m.text == "🧾 Мои заявки")
async def my_requests(msg: types.Message):
    cursor.execute(
        "SELECT id, service, amount, exact_amount, status FROM requests WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (msg.from_user.id,)
    )
    rows = cursor.fetchall()
    if not rows:
        await msg.answer("У вас пока нет заявок.")
        return
    text = "\n".join(
        f"#{r[0]} {r[1]}: {r[2]}"
        + (f"/{r[3]}" if r[3] else "")
        + f" — {r[4]}"
        for r in rows
    )
    await msg.answer("Ваши заявки:\n" + text)


@dp.message_handler()
async def process_flow(msg: types.Message):
    uid = msg.from_user.id
    state = user_states.get(uid)
    if not state:
        return  # ничего не ждём

    text = msg.text.strip()
    srv = state["service"]
    step = state["step"]

    # 1) Получили номер карты
    if step == "card":
        state["card"] = text
        state["step"] = "xbet"
        await msg.answer("Введите ваш ID 1xBet:")
        return

    # 2) Получили ID 1xBet
    if step == "xbet":
        state["xbet_id"] = text
        state["step"] = "amount"
        await msg.answer(f"Введите сумму ({MIN_AMOUNT}-{MAX_AMOUNT}):")
        return

    # 3) Получили сумму
    if step == "amount":
        if not text.isdigit():
            return await msg.answer("Пожалуйста, введите число.")
        amount = int(text)
        if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
            return await msg.answer(f"Сумма должна быть от {MIN_AMOUNT} до {MAX_AMOUNT}.")
        state["amount"] = amount

        # Создаём заявку
        exact = None
        card_to_pay = None
        if srv == "Пополнение":
            # генерируем точную сумму
            exact = amount + random.randint(1, 9)
            card_to_pay = get_active_card()
            if not card_to_pay:
                return await msg.answer("Извините, сейчас нет активных карт. Обратитесь к администратору.")
        else:
            # вывод: карта уже в state["card"]
            card_to_pay = state["card"]

        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO requests (user_id, service, amount, exact_amount, xbet_id, card, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'ожидает', ?)",
            (uid, srv, amount, exact, state["xbet_id"], card_to_pay, created)
        )
        conn.commit()
        req_id = cursor.lastrowid
        user_states.pop(uid)

        # Отправляем инструкцию
        if srv == "Пополнение":
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{req_id}")
            )
            await msg.answer(
                "❗️ Переведите точную сумму:\n\n"
                f"<b>{exact} UZS</b>\n"
                f"Карта для перевода: <code>{card_to_pay}</code>\n"
                f"Не переводить: {amount} UZS\n\n"
                f"После перевода нажмите «Я оплатил» в течение 15 минут.\n\n"
                f"TG_ID: {uid}   Заявка: #{req_id}",
                parse_mode="HTML",
                reply_markup=kb
            )
        else:
            await msg.answer(f"Заявка на вывод #{req_id} принята. Ожидайте обработки.")
        return


@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def on_paid(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET status='на проверке' WHERE id=?", (rid,))
    conn.commit()
    await callback.answer("Статус: на проверке")
    await callback.message.answer("Отправьте чек (фото или PDF) в ответ на это сообщение.")


@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT])
async def receive_check(msg: types.Message):
    cursor.execute(
        "SELECT id FROM requests WHERE user_id=? AND status='на проверке' ORDER BY id DESC LIMIT 1",
        (msg.from_user.id,)
    )
    row = cursor.fetchone()
    if not row:
        return
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    cursor.execute("UPDATE requests SET file_id=?, status='ожидает' WHERE id=?", (file_id, row[0]))
    conn.commit()
    await msg.answer("Чек сохранён. Ожидайте подтверждения администратора.")


@dp.message_handler(commands=["addcard"])
async def cmd_addcard(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    parts = msg.text.split()
    if len(parts) != 2:
        return await msg.answer("Использование: /addcard 9860123412341234")
    num = parts[1]
    cursor.execute("INSERT INTO cards (number) VALUES (?)", (num,))
    conn.commit()
    await msg.answer(f"Карта {num} добавлена.")


@dp.message_handler(commands=["cards"])
async def cmd_cards(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    cursor.execute("SELECT id, number, active, usage_count FROM cards")
    rows = cursor.fetchall()
    if not rows:
        return await msg.answer("Нет карт в базе.")
    text = "\n".join(
        f"{r[0]}: {r[1]}  {'✅' if r[2] else '❌'}  used {r[3]}"
        for r in rows
    )
    await msg.answer("Карты:\n" + text)


@dp.message_handler(commands=["admin"])
async def cmd_admin(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    cursor.execute(
        "SELECT id, service, amount, exact_amount, status FROM requests ORDER BY id DESC LIMIT 10"
    )
    rows = cursor.fetchall()
    if not rows:
        return await msg.answer("Нет заявок.")
    for r in rows:
        rid, srv, amt, ex, st = r
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"ok_{rid}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{rid}")
        )
        txt = f"#{rid} {srv} {amt}"
        if ex: txt += f"/{ex}"
        txt += f" — {st}"
        await msg.answer(txt, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
async def on_admin_decide(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    decision = "подтверждено" if callback.data.startswith("ok_") else "отклонено"
    cursor.execute("UPDATE requests SET status=? WHERE id=?", (decision, rid))
    conn.commit()
    await callback.answer(f"Заявка {rid} {decision}")
    # обновим текст кнопок
    await callback.message.edit_text(callback.message.text + f" → {decision}")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
