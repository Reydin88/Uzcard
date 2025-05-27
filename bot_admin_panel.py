from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
import sqlite3, os
from datetime import datetime
import pandas as pd

BOT_TOKEN = "8077158709:AAFDbx2Ek7WhAA6WBiIOWrLuMpAserStCo0"
ADMIN_IDS = [1236771535]
LOG_GROUP_ID = -1000000000000  # ← сюда вставь ID своей лог-группы, если нужна отправка логов

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cursor = conn.cursor()

# ===== КНОПКИ =====
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("Пополнение", "Вывод")

@dp.message_handler(commands=["start"])
async def start_handler(msg: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (msg.from_user.id,))
    await msg.answer("Выберите услугу:", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == "Пополнение")
async def start_topup(msg: types.Message):
    uid = msg.from_user.id
    cursor.execute("SELECT * FROM requests WHERE user_id = ? AND status IN ('ожидает', 'на проверке')", (uid,))
    if cursor.fetchone():
        return await msg.answer("У вас уже есть активная заявка. Завершите её перед созданием новой.")
    await msg.answer("Введите сумму пополнения в сумах (например, 100000):")
    dp.register_message_handler(process_amount, state="amount")

async def process_amount(msg: types.Message):
    try:
        amount = int(msg.text)
        if amount < 10000 or amount > 1000000:
            return await msg.answer("Сумма должна быть от 10 000 до 1 000 000 сум.")
        await msg.answer("Введите ваш ID 1xBet:")
        dp.register_message_handler(lambda m: process_id(m, amount), state="id")
    except:
        await msg.answer("Неверный формат суммы.")

async def process_id(msg: types.Message, amount):
    xbet_id = msg.text.strip()
    card_to_pay = get_active_card()
    req_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO requests (user_id, service, amount, xbet_id, status, created_at, sender_card)
        VALUES (?, 'Пополнение', ?, ?, 'ожидает', ?, '')
    """, (msg.from_user.id, amount, xbet_id, req_time))
    conn.commit()
    req_id = cursor.lastrowid
    await msg.answer(
        f"Ваша заявка №{req_id} создана.\n\n"
        f"Переведите {amount} сум на карту:\n<code>{card_to_pay}</code>\n"
        f"Затем нажмите /paid_{req_id}",
        parse_mode="HTML"
    )

def get_active_card():
    cursor.execute("SELECT id, number FROM cards WHERE active = 1 ORDER BY usage_count ASC LIMIT 1")
    card = cursor.fetchone()
    if card:
        cursor.execute("UPDATE cards SET usage_count = usage_count + 1 WHERE id = ?", (card[0],))
        conn.commit()
        return card[1]
    return "9860 0000 0000 0000"

@dp.message_handler(lambda m: m.text.startswith("/paid_"))
async def paid_handler(msg: types.Message):
    uid = msg.from_user.id
    req_id = msg.text.split("_")[1]
    cursor.execute("SELECT status FROM requests WHERE id = ? AND user_id = ?", (req_id, uid))
    row = cursor.fetchone()
    if not row:
        return await msg.reply("Заявка не найдена.")
    if row[0] != "ожидает":
        return await msg.reply("Эта заявка уже была обработана.")
    cursor.execute("UPDATE requests SET status = 'на проверке', paid_at = CURRENT_TIMESTAMP WHERE id = ?", (req_id,))
    conn.commit()
    await msg.answer("Теперь отправьте чек в ответ на это сообщение (фото или PDF).")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receive_photo(msg: types.Message):
    uid = msg.from_user.id
    cursor.execute("SELECT id FROM requests WHERE user_id = ? AND status = 'на проверке' ORDER BY id DESC LIMIT 1", (uid,))
    row = cursor.fetchone()
    if not row:
        return await msg.reply("Нет ожидающей заявки.")
    file_id = msg.photo[-1].file_id
    cursor.execute("UPDATE requests SET file1 = ? WHERE id = ?", (file_id, row[0]))
    conn.commit()
    await msg.reply("Чек получен. Ожидайте подтверждение.")

@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def receive_doc(msg: types.Message):
    uid = msg.from_user.id
    cursor.execute("SELECT id FROM requests WHERE user_id = ? AND status = 'на проверке' ORDER BY id DESC LIMIT 1", (uid,))
    row = cursor.fetchone()
    if not row:
        return await msg.reply("Нет ожидающей заявки.")
    file_id = msg.document.file_id
    cursor.execute("UPDATE requests SET file2 = ? WHERE id = ?", (file_id, row[0]))
    conn.commit()
    await msg.reply("Файл получен.")

@dp.message_handler(commands=["status"])
async def my_status(msg: types.Message):
    uid = msg.from_user.id
    cursor.execute("SELECT id, status FROM requests WHERE user_id = ? ORDER BY id DESC LIMIT 1", (uid,))
    row = cursor.fetchone()
    if not row:
        return await msg.reply("У вас нет заявок.")
    await msg.reply(f"Заявка #{row[0]}: {row[1]}")

@dp.message_handler(commands=["confirm", "reject"])
async def admin_decision(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Формат: /confirm ID или /reject ID причина")
    cmd, rid = parts[0], parts[1]
    if not rid.isdigit():
        return await msg.reply("ID должен быть числом.")
    status = "подтверждено" if "confirm" in cmd else "отклонено"
    reason = " ".join(parts[2:]) if status == "отклонено" else ""
    cursor.execute("UPDATE requests SET status = ? WHERE id = ?", (status, rid))
    conn.commit()
    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (rid,))
    user_id = cursor.fetchone()[0]
    await bot.send_message(user_id, f"Ваша заявка #{rid} {status}.\n" + (f"Причина: {reason}" if reason else ""))
    await msg.reply(f"Заявка {rid} {status}.")

@dp.callback_query_handler(lambda c: c.data.startswith("check_"))
async def show_check(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("SELECT file1, file2 FROM requests WHERE id = ?", (rid,))
    files = cursor.fetchone()
    if not files or (not files[0] and not files[1]):
        return await callback.answer("Чек не найден.")
    await callback.message.answer(f"Чеки по заявке #{rid}:")
    if files[0]:
        await bot.send_photo(callback.from_user.id, files[0])
    if files[1]:
        await bot.send_document(callback.from_user.id, files[1])

@dp.callback_query_handler(lambda c: c.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET status = 'подтверждено' WHERE id = ?", (rid,))
    conn.commit()
    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (rid,))
    user_id = cursor.fetchone()[0]
    await bot.send_message(user_id, f"Ваша заявка #{rid} подтверждена.")
    await callback.answer("Подтверждено.")
    await callback.message.edit_reply_markup()

@dp.callback_query_handler(lambda c: c.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET status = 'отклонено' WHERE id = ?", (rid,))
    conn.commit()
    cursor.execute("SELECT user_id FROM requests WHERE id = ?", (rid,))
    user_id = cursor.fetchone()[0]
    await bot.send_message(user_id, f"Ваша заявка #{rid} отклонена.")
    await callback.answer("Отклонено.")
    await callback.message.edit_reply_markup()

@dp.callback_query_handler(lambda c: c.data == "admin_requests")
async def list_requests(callback: types.CallbackQuery):
    cursor.execute("SELECT id, user_id, amount, xbet_id, status FROM requests ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    for r in rows:
        rid, uid, amount, xbet, status = r
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_{rid}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{rid}")
        )
        kb.add(InlineKeyboardButton("📎 Чек", callback_data=f"check_{rid}"))
        text = f"#{rid} | {amount} сум | ID: {xbet}\nСтатус: {status}\nПользователь: {uid}"
        await callback.message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "admin_cards")
async def admin_cards(callback: types.CallbackQuery):
    cursor.execute("SELECT id, number, active FROM cards ORDER BY id")
    cards = cursor.fetchall()
    for c in cards:
        cid, number, active = c
        status = "✅" if active else "❌"
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("Вкл/Выкл", callback_data=f"togglecard_{cid}"),
            InlineKeyboardButton("Удалить", callback_data=f"delcard_{cid}")
        )
        await callback.message.answer(f"{status} {number} (ID: {cid})", reply_markup=kb)
    await callback.message.answer("➕ Добавить карту", reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("Ввести номер", callback_data="add_card_start")
    ))

@dp.callback_query_handler(lambda c: c.data.startswith("togglecard_"))
async def toggle_card_callback(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE cards SET active = 1 - active WHERE id = ?", (cid,))
    conn.commit()
    await callback.answer("Статус переключён.")
    await callback.message.edit_reply_markup()

@dp.callback_query_handler(lambda c: c.data.startswith("delcard_"))
async def delete_card_callback(callback: types.CallbackQuery):
    cid = int(callback.data.split("_")[1])
    cursor.execute("DELETE FROM cards WHERE id = ?", (cid,))
    conn.commit()
    await callback.answer("Карта удалена.")
    await callback.message.edit_reply_markup()

# Добавление карты вручную
adding_card = {}

@dp.callback_query_handler(lambda c: c.data == "add_card_start")
async def start_add_card(callback: types.CallbackQuery):
    await callback.message.answer("Введите номер карты (например, 9860XXXXXXXXXXXX):")
    adding_card[callback.from_user.id] = True

@dp.message_handler()
async def handle_new_card(message: types.Message):
    if adding_card.get(message.from_user.id):
        card = message.text.strip()
        if not card.startswith("9860") or len(card) < 16:
            return await message.reply("Неверный формат карты.")
        cursor.execute("INSERT INTO cards (number) VALUES (?)", (card,))
        conn.commit()
        adding_card.pop(message.from_user.id)
        return await message.reply("Карта добавлена.")
