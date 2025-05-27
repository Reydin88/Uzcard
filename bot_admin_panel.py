from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime

BOT_TOKEN = "7878879986:AAEnUlGIKo6MYyzsqny20qnX9adlITGF--s"
ADMIN_IDS = [1236771535]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
conn = sqlite3.connect("db.sqlite3", check_same_thread=False)
cursor = conn.cursor()

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("Пополнение", "Вывод")

user_states = {}

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    user_states.pop(msg.from_user.id, None)
    await msg.answer("Выберите услугу:", reply_markup=main_kb)

@dp.message_handler(lambda m: m.text == "Пополнение")
async def handle_topup(msg: types.Message):
    user_states[msg.from_user.id] = {"step": "amount", "service": "Пополнение"}
    await msg.answer("Введите сумму пополнения:")

@dp.message_handler(lambda m: m.text == "Вывод")
async def handle_withdraw(msg: types.Message):
    user_states[msg.from_user.id] = {"step": "amount", "service": "Вывод"}
    await msg.answer("Введите сумму для вывода:")

@dp.message_handler()
async def handle_input(msg: types.Message):
    uid = msg.from_user.id
    if uid not in user_states:
        return
    state = user_states[uid]
    step = state.get("step")
    service = state.get("service")

    if step == "amount":
        try:
            amount = int(msg.text)
            if amount < 1000 or amount > 10000000:
                return await msg.answer("Сумма от 1 000 до 10 000 000.")
            state["amount"] = amount
            state["step"] = "xbet_id"
            return await msg.answer("Введите ID 1xBet:")
        except:
            return await msg.answer("Введите число.")

    elif step == "xbet_id":
        state["xbet_id"] = msg.text.strip()
        if service == "Пополнение":
            state["step"] = "confirm"
            card = get_active_card()
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO requests (user_id, service, amount, xbet_id, status, created_at) VALUES (?, ?, ?, ?, 'ожидает', ?)",
                           (uid, service, state["amount"], state["xbet_id"], created_at))
            conn.commit()
            req_id = cursor.lastrowid
            user_states.pop(uid)
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{req_id}")
            )
            return await msg.answer(
                f"Переведите <b>{state['amount']} сум</b> на карту:"

f"<code>{card}</code>"
                f"Затем нажмите кнопку ниже.",
                parse_mode="HTML", reply_markup=kb)
        else:
            state["step"] = "card"
            return await msg.answer("Введите номер карты получателя:")

    elif step == "card":
        state["card"] = msg.text.strip()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO requests (user_id, service, amount, xbet_id, card_receiver, status, created_at) VALUES (?, ?, ?, ?, ?, 'ожидает', ?)",
                       (uid, "Вывод", state["amount"], state["xbet_id"], state["card"], created_at))
        conn.commit()
        req_id = cursor.lastrowid
        user_states.pop(uid)
        return await msg.answer(f"Заявка #{req_id} на вывод создана. Ожидайте подтверждение.")

@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def mark_paid(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    cursor.execute("UPDATE requests SET status = 'на проверке' WHERE id = ?", (rid,))
    conn.commit()
    await callback.message.answer("Теперь отправьте чек (фото или PDF).")
    await callback.answer()

@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.DOCUMENT])
async def receive_file(msg: types.Message):
    uid = msg.from_user.id
    cursor.execute("SELECT id FROM requests WHERE user_id = ? AND status = 'на проверке' ORDER BY id DESC LIMIT 1", (uid,))
    row = cursor.fetchone()
    if not row:
        return await msg.reply("Нет активной заявки.")
    file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
    cursor.execute("UPDATE requests SET file1 = ? WHERE id = ?", (file_id, row[0]))
    conn.commit()
    await msg.reply("Чек получен. Ожидайте подтверждение.")

@dp.message_handler(commands=["admin"])
async def admin_panel(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    cursor.execute("SELECT id, service, amount, xbet_id, card_receiver, status FROM requests ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    for r in rows:
        rid, srv, amount, xid, card, status = r
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"ok_{rid}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"no_{rid}")
        )
        txt = f"#{rid} | {srv} | {amount} сум | ID: {xid}\n"
        if srv == "Вывод":
            txt += f"Получатель: {card}\n"
        txt += f"Статус: {status}"
        await msg.answer(txt, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("ok_") or c.data.startswith("no_"))
async def admin_action(callback: types.CallbackQuery):
    rid = int(callback.data.split("_")[1])
    status = "подтверждено" if "ok" in callback.data else "отклонено"
    cursor.execute("UPDATE requests SET status = ? WHERE id = ?", (status, rid))
    conn.commit()
    await callback.message.edit_text(f"Заявка #{rid} {status}")
    await callback.answer()

def get_active_card():
    cursor.execute("SELECT id, number FROM cards WHERE active = 1 ORDER BY usage_count ASC LIMIT 1")
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE cards SET usage_count = usage_count + 1 WHERE id = ?", (row[0],))
        conn.commit()
        return row[1]
    return "9860 0000 0000 0000"

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
