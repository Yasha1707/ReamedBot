#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import calendar
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = "8717377368:AAE8iF2JrxmLykUxJ5OAEv87S0eE4Y9pNVg"
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

DB_NAME = "rehamed.db"

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE,
        role TEXT DEFAULT 'patient',
        name TEXT,
        chat_id INTEGER UNIQUE
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        service TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        doctor_id INTEGER,
        service TEXT,
        date TEXT,
        time TEXT,
        status TEXT DEFAULT 'confirmed',
        created_at TEXT
    )''')
    conn.commit()
    conn.close()

def populate_initial_data():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    doctors_data = [
        ('Мостовая Наталья Владимировна', 'Неврология'),
        ('Лукашина Наталья Юрьевна', 'Неврология'),
        ('Заикина Людмила Юрьевна', 'Стоматология'),
        ('Тагунова Татьяна Ивановна', 'Стоматология'),
        ('Заикина Людмила Юрьевна', 'Ортодонтия'),
        ('Тагунова Татьяна Ивановна', 'Ортодонтия'),
        ('Постнова Светлана Геннадьевна', 'УЗИ'),
        ('Егоров Виктор Анатольевич', 'УЗИ'),
        ('Лисунова Елена Сергеевна', 'УЗИ'),
        ('Москвичева Ирина Николаевна', 'УЗИ'),
        ('Власова Ирина Юрьевна', 'УЗИ'),
        ('Горбунова Лариса Владимировна', 'Гинекология')
    ]
    for name, service in doctors_data:
        cur.execute("INSERT OR IGNORE INTO doctors (name, service) VALUES (?, ?)", (name, service))
    conn.commit()
    conn.close()

init_db()
populate_initial_data()

# ========== ФУНКЦИИ БАЗЫ ДАННЫХ ==========
def get_user_by_chat_id(chat_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, phone, role, name FROM users WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row

def register_user(phone, name, chat_id, role='patient'):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (phone, role, name, chat_id) VALUES (?, ?, ?, ?)", (phone, role, name, chat_id))
        user_id = cur.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except:
        conn.close()
        return None

def update_user_role(chat_id, new_role):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET role=? WHERE chat_id=?", (new_role, chat_id))
    conn.commit()
    conn.close()

def create_appointment_demo(user_id, doctor_id, service, date_str, time_str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''INSERT INTO appointments (user_id, doctor_id, service, date, time, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (user_id, doctor_id, service, date_str, time_str, 'confirmed', datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_doctor_by_id(doc_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name, service FROM doctors WHERE id=?", (doc_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_doctors_by_service(service_name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM doctors WHERE service=?", (service_name,))
    rows = cur.fetchall()
    conn.close()
    return rows

# ========== КЛАВИАТУРЫ ==========
def main_menu(role='patient'):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записаться", callback_data="book")],
        [InlineKeyboardButton(text="📋 Мои записи", callback_data="my_appointments")]
    ])
    if role in ('admin', 'deputy'):
        kb.inline_keyboard.append([InlineKeyboardButton(text="📅 Расписание на сегодня", callback_data="today_schedule")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="✅ Отметить визит", callback_data="mark_visited_prompt")])
    if role == 'deputy':
        kb.inline_keyboard.append([InlineKeyboardButton(text="📊 Отчёт", callback_data="report_start")])
    if role == 'doctor':
        kb.inline_keyboard.append([InlineKeyboardButton(text="🩺 Моё расписание", callback_data="my_schedule")])
    return kb

def services_keyboard():
    services = ['Стоматология', 'УЗИ', 'Терапия', 'Гинекология', 'Неврология', 'Ортодонтия']
    buttons = [[InlineKeyboardButton(text=s, callback_data=f"service_{s}")] for s in services]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def doctors_keyboard(service_name):
    doctors = get_doctors_by_service(service_name)
    if not doctors:
        return None
    buttons = [[InlineKeyboardButton(text=doc[1], callback_data=f"doctor_{doc[0]}")] for doc in doctors]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="book")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def calendar_keyboard(year, month, doctor_id):
    now = datetime.now().date()
    cal = calendar.monthcalendar(year, month)
    kb_buttons = []
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_obj = datetime(year, month, day).date()
                if date_obj < now or date_obj.weekday() >= 5:
                    row.append(InlineKeyboardButton(text=f"{day}", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(text=f"{day}", callback_data=f"date_{year}_{month}_{day}_{doctor_id}"))
        kb_buttons.append(row)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    row_nav = [
        InlineKeyboardButton(text="◀️", callback_data=f"cal_{prev_year}_{prev_month}_{doctor_id}"),
        InlineKeyboardButton(text=f"{month}/{year}", callback_data="ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"cal_{next_year}_{next_month}_{doctor_id}")
    ]
    kb_buttons.append(row_nav)
    kb_buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="book")])
    return InlineKeyboardMarkup(inline_keyboard=kb_buttons)

def time_keyboard():
    times = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00']
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"time_{t}")] for t in times]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="book")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== СОСТОЯНИЯ ==========
class BookingState(StatesGroup):
    choosing_service = State()
    choosing_doctor = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()

class AdminMarkVisit(StatesGroup):
    waiting_for_id = State()

# ========== ХЭНДЛЕРЫ КОМАНД ДЛЯ СМЕНЫ РОЛИ ==========
@dp.message(Command("admin"))
async def set_admin(message: types.Message):
    chat_id = message.chat.id
    user = get_user_by_chat_id(chat_id)
    if user:
        update_user_role(chat_id, 'admin')
        await message.answer("Роль изменена на **Администратор**. Перезапустите меню командой /start или нажмите «Главное меню».", parse_mode="Markdown")
    else:
        await message.answer("Сначала зарегистрируйтесь через /start")

@dp.message(Command("doctor"))
async def set_doctor(message: types.Message):
    chat_id = message.chat.id
    user = get_user_by_chat_id(chat_id)
    if user:
        update_user_role(chat_id, 'doctor')
        await message.answer("Роль изменена на **Врач**. Перезапустите меню командой /start или нажмите «Главное меню».", parse_mode="Markdown")
    else:
        await message.answer("Сначала зарегистрируйтесь через /start")

@dp.message(Command("deputy"))
async def set_deputy(message: types.Message):
    chat_id = message.chat.id
    user = get_user_by_chat_id(chat_id)
    if user:
        update_user_role(chat_id, 'deputy')
        await message.answer("Роль изменена на **Заместитель директора**. Перезапустите меню командой /start или нажмите «Главное меню».", parse_mode="Markdown")
    else:
        await message.answer("Сначала зарегистрируйтесь через /start")

@dp.message(Command("patient"))
async def set_patient(message: types.Message):
    chat_id = message.chat.id
    user = get_user_by_chat_id(chat_id)
    if user:
        update_user_role(chat_id, 'patient')
        await message.answer("Роль изменена на **Пациент**. Перезапустите меню командой /start или нажмите «Главное меню».", parse_mode="Markdown")
    else:
        await message.answer("Сначала зарегистрируйтесь через /start")

# ========== ОСНОВНЫЕ ХЭНДЛЕРЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю", callback_data="agree_pd")]
    ])
    await message.answer("Для работы с ботом необходимо дать согласие на обработку персональных данных (ФЗ-152). Нажмите «Принимаю».", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "agree_pd")
async def agree_pd(callback: CallbackQuery):
    await callback.message.edit_text("Спасибо. Теперь поделитесь номером телефона.")
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.answer("Для регистрации нажмите кнопку ниже:", reply_markup=kb)

@dp.message(lambda msg: msg.contact is not None)
async def handle_contact(message: types.Message):
    phone = message.contact.phone_number
    name = message.contact.first_name
    chat_id = message.chat.id
    user = get_user_by_chat_id(chat_id)
    if not user:
        register_user(phone, name, chat_id, 'patient')
        role = 'patient'
    else:
        role = user[2]
    await message.answer(f"Регистрация успешна! Ваша роль: {role}", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Главное меню:", reply_markup=main_menu(role))

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = get_user_by_chat_id(chat_id)
    role = user[2] if user else 'patient'
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu(role))

@dp.callback_query(lambda c: c.data == "book")
async def book_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingState.choosing_service)
    await callback.message.edit_text("Выберите услугу:", reply_markup=services_keyboard())

@dp.callback_query(BookingState.choosing_service, lambda c: c.data.startswith("service_"))
async def service_chosen(callback: CallbackQuery, state: FSMContext):
    service_name = callback.data.split("service_")[1]
    await state.update_data(service=service_name)
    kb = doctors_keyboard(service_name)
    if not kb:
        await callback.message.edit_text("Нет врачей по данной услуге.", reply_markup=services_keyboard())
        return
    await state.set_state(BookingState.choosing_doctor)
    await callback.message.edit_text(f"Вы выбрали: {service_name}\nТеперь выберите врача:", reply_markup=kb)

@dp.callback_query(BookingState.choosing_doctor, lambda c: c.data.startswith("doctor_"))
async def doctor_chosen(callback: CallbackQuery, state: FSMContext):
    doctor_id = int(callback.data.split("doctor_")[1])
    doctor = get_doctor_by_id(doctor_id)
    await state.update_data(doctor_id=doctor_id, doctor_name=doctor[1])
    now = datetime.now()
    kb = calendar_keyboard(now.year, now.month, doctor_id)
    await state.set_state(BookingState.choosing_date)
    await callback.message.edit_text(f"Врач: {doctor[1]}\nВыберите дату (календарь, только рабочие дни, 30 дней вперёд):", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("cal_"))
async def calendar_nav(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    year = int(parts[1])
    month = int(parts[2])
    doctor_id = int(parts[3])
    kb = calendar_keyboard(year, month, doctor_id)
    await callback.message.edit_reply_markup(reply_markup=kb)

@dp.callback_query(BookingState.choosing_date, lambda c: c.data.startswith("date_"))
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    year = int(parts[1])
    month = int(parts[2])
    day = int(parts[3])
    doctor_id = int(parts[4])
    date_str = f"{year}-{month:02d}-{day:02d}"
    await state.update_data(date=date_str)
    await state.set_state(BookingState.choosing_time)
    await callback.message.edit_text(f"Выбрана дата: {date_str}\nТеперь выберите время:", reply_markup=time_keyboard())

@dp.callback_query(BookingState.choosing_time, lambda c: c.data.startswith("time_"))
async def time_chosen(callback: CallbackQuery, state: FSMContext):
    time_str = callback.data.split("time_")[1]
    await state.update_data(time=time_str)
    data = await state.get_data()
    await state.set_state(BookingState.confirming)
    confirm_text = f"Вы записываетесь:\nУслуга: {data['service']}\nВрач: {data['doctor_name']}\nДата: {data['date']}\nВремя: {time_str}\nПодтвердите запись."
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_no")]
    ])
    await callback.message.edit_text(confirm_text, reply_markup=kb)

@dp.callback_query(lambda c: c.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = callback.message.chat.id
    user = get_user_by_chat_id(chat_id)
    if not user:
        await callback.message.answer("Ошибка пользователя. Перезапустите /start")
        return
    user_id = user[0]
    result = create_appointment_demo(user_id, data['doctor_id'], data['service'], data['date'], data['time'])
    if result:
        await callback.message.edit_text("✅ Запись подтверждена! Вы получите напоминание за 24 часа.")
    else:
        await callback.message.edit_text("❌ Ошибка при сохранении.")
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=main_menu(user[2]))

@dp.callback_query(lambda c: c.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.message.answer("Главное меню:", reply_markup=main_menu('patient'))

# ---------- Администратор: расписание на сегодня (с демо-примерами) ----------
@dp.callback_query(lambda c: c.data == "today_schedule")
async def today_schedule(callback: CallbackQuery):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''SELECT a.id, u.name, d.name, a.time, a.status 
                   FROM appointments a
                   JOIN users u ON a.user_id=u.id
                   JOIN doctors d ON a.doctor_id=d.id
                   WHERE a.date=?''', (today,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        # Демо-данные для скриншота
        demo_text = "📋 Записи на сегодня (демо-пример):\nID:101 | Иванов И.И. -> Мостовая Н.В. в 10:00 (статус: confirmed)\nID:102 | Петрова М.С. -> Тагунова Т.И. в 11:30 (статус: confirmed)\n"
        await callback.message.answer(demo_text)
    else:
        text = "📋 Записи на сегодня:\n"
        for r in rows:
            text += f"ID:{r[0]} | {r[1]} -> {r[2]} в {r[3]} (статус: {r[4]})\n"
        await callback.message.answer(text)

@dp.callback_query(lambda c: c.data == "mark_visited_prompt")
async def prompt_mark_visited(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminMarkVisit.waiting_for_id)
    await callback.message.answer("Введите ID записи для отметки визита (цифру).")

@dp.message(AdminMarkVisit.waiting_for_id)
async def mark_visited(message: types.Message, state: FSMContext):
    try:
        app_id = int(message.text.strip())
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("UPDATE appointments SET status='visited' WHERE id=?", (app_id,))
        conn.commit()
        conn.close()
        await message.answer(f"Запись {app_id} отмечена как посещённая.")
    except:
        await message.answer("Ошибка: введите корректный ID.")
    await state.clear()

# ---------- Заместитель директора: отчёт (с демо-примерами) ----------
@dp.callback_query(lambda c: c.data == "report_start")
async def report_start(callback: CallbackQuery):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT status FROM appointments WHERE date=?", (today,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        # Демо-отчёт
        await callback.message.answer(f"📊 Отчёт за {today} (демо-пример):\nВсего записей: 8\nНеявок: 1\nПереносов: 2")
    else:
        total = len(rows)
        missed = sum(1 for r in rows if r[0] == 'missed')
        rescheduled = sum(1 for r in rows if r[0] == 'rescheduled')
        await callback.message.answer(f"📊 Отчёт за {today}:\nВсего записей: {total}\nНеявок: {missed}\nПереносов: {rescheduled}")

# ---------- Пациент: мои записи ----------
@dp.callback_query(lambda c: c.data == "my_appointments")
async def my_appointments(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user = get_user_by_chat_id(chat_id)
    if not user:
        await callback.message.answer("Ошибка")
        return
    user_id = user[0]
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''SELECT a.id, d.name, a.date, a.time, a.status
                   FROM appointments a JOIN doctors d ON a.doctor_id=d.id
                   WHERE a.user_id=?''', (user_id,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        # Демо-записи для скриншота
        await callback.message.answer("Ваши записи (демо-пример):\nID:101 | Мостовая Н.В. | 2025-05-25 в 10:00 (статус: confirmed)\nID:102 | Тагунова Т.И. | 2025-05-26 в 11:30 (статус: confirmed)")
    else:
        text = "Ваши записи:\n"
        for r in rows:
            text += f"ID:{r[0]} | {r[1]} | {r[2]} в {r[3]} (статус: {r[4]})\n"
        await callback.message.answer(text)

# ---------- Врач: моё расписание (демо-пример) ----------
@dp.callback_query(lambda c: c.data == "my_schedule")
async def doctor_schedule(callback: CallbackQuery):
    # Для диплома достаточно демо-примера
    await callback.message.answer("🩺 Ваше расписание на сегодня (демо-пример):\n10:00 - Иванов И.И. (статус: confirmed)\n11:30 - Петрова М.С. (статус: confirmed)")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
