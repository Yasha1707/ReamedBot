#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import calendar
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8717377368:AAE8iF2JrxmLykUxJ5OAEv87S0eE4Y9pNVg"   # замените на ваш токен

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# ==================== БАЗА ДАННЫХ ====================
DB_NAME = "rehamed.db"

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
    cur.execute('''CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_id INTEGER,
        date TEXT,
        time TEXT,
        is_free INTEGER DEFAULT 1,
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        doctor_id INTEGER,
        service TEXT,
        date TEXT,
        time TEXT,
        status TEXT DEFAULT 'confirmed',
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    )''')
    conn.commit()
    conn.close()

def populate_initial_data():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    # Услуги
    services = ['Стоматология', 'УЗИ', 'Терапия', 'Гинекология', 'Неврология', 'Ортодонтия']
    for s in services:
        cur.execute("INSERT OR IGNORE INTO services (name) VALUES (?)", (s,))
    # Врачи
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

# ==================== РАБОТА С БАЗОЙ ====================
def get_user_by_chat_id(chat_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, role, name, phone FROM users WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row

def register_user(chat_id, phone, name=None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (chat_id, phone, role, name) VALUES (?, ?, 'patient', ?)", (chat_id, phone, name))
        user_id = cur.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except:
        conn.close()
        return None

def get_user_by_phone(phone):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, role, name, chat_id FROM users WHERE phone=?", (phone,))
    row = cur.fetchone()
    conn.close()
    return row

def update_user_chat_id(phone, chat_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE users SET chat_id=? WHERE phone=?", (chat_id, phone))
    conn.commit()
    conn.close()

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

def get_free_slots(doctor_id, date_str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT time FROM slots WHERE doctor_id=? AND date=? AND is_free=1", (doctor_id, date_str))
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

def create_appointment(user_id, doctor_id, service, date_str, time_str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id FROM slots WHERE doctor_id=? AND date=? AND time=? AND is_free=1", (doctor_id, date_str, time_str))
    slot = cur.fetchone()
    if not slot:
        conn.close()
        return False
    cur.execute("UPDATE slots SET is_free=0 WHERE doctor_id=? AND date=? AND time=?", (doctor_id, date_str, time_str))
    cur.execute('''INSERT INTO appointments (user_id, doctor_id, service, date, time, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (user_id, doctor_id, service, date_str, time_str, 'confirmed', datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def add_slot(doctor_id, date_str, time_str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO slots (doctor_id, date, time, is_free) VALUES (?, ?, ?, 1)", (doctor_id, date_str, time_str))
    conn.commit()
    conn.close()

def get_user_role(user_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 'patient'

# ==================== КЛАВИАТУРЫ ====================
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
                if date_obj < now or date_obj.weekday() >= 5:   # выходные – суббота, воскресенье
                    row.append(InlineKeyboardButton(text=f"{day}", callback_data="ignore"))
                else:
                    row.append(InlineKeyboardButton(text=f"{day}", callback_data=f"date_{year}_{month}_{day}_{doctor_id}"))
        kb_buttons.append(row)
    # навигация
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

def time_slots_keyboard(slots):
    if not slots:
        return None
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"time_{t}")] for t in slots]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="book")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def request_contact_keyboard():
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return kb

# ==================== СОСТОЯНИЯ ====================
class BookingState(StatesGroup):
    choosing_service = State()
    choosing_doctor = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()

class AdminMarkVisit(StatesGroup):
    waiting_for_id = State()

# ==================== ХЭНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Проверим, есть ли уже пользователь с таким chat_id
    user = get_user_by_chat_id(message.chat.id)
    if user:
        role = user[1]
        await message.answer(f"Добро пожаловать! Ваша роль: {role}", reply_markup=main_menu(role))
    else:
        # Запрашиваем контакт обычной reply-клавиатурой
        await message.answer("Для работы с ботом необходимо поделиться номером телефона. Нажмите кнопку ниже.", reply_markup=request_contact_keyboard())

@dp.message(lambda msg: msg.contact is not None)
async def handle_contact(message: types.Message):
    phone = message.contact.phone_number
    name = message.contact.first_name
    user = get_user_by_phone(phone)
    chat_id = message.chat.id
    if not user:
        # Регистрируем нового пользователя
        user_id = register_user(chat_id, phone, name)
        role = 'patient'
    else:
        # Обновляем chat_id для существующего пользователя
        user_id = user[0]
        role = user[1]
        update_user_chat_id(phone, chat_id)
    await message.answer(f"Регистрация успешна! Ваша роль: {role}", reply_markup=main_menu(role))

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    # Получаем роль пользователя
    user = get_user_by_chat_id(callback.message.chat.id)
    role = user[1] if user else 'patient'
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
        await callback.message.edit_text("Нет врачей по данной услуге. Выберите другую.", reply_markup=services_keyboard())
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
    await callback.message.edit_text(f"Врач: {doctor[1]}\nВыберите дату (только рабочие дни, вперёд на месяц):", reply_markup=kb)

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
    slots = get_free_slots(doctor_id, date_str)
    if not slots:
        await callback.message.answer("На эту дату нет свободных слотов. Попробуйте другую дату.")
        return
    kb = time_slots_keyboard(slots)
    await state.set_state(BookingState.choosing_time)
    await callback.message.edit_text(f"Выбрана дата: {date_str}\nДоступное время:", reply_markup=kb)

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
    user = get_user_by_chat_id(callback.message.chat.id)
    if not user:
        await callback.message.answer("Ошибка: пользователь не найден.")
        await state.clear()
        return
    user_id = user[0]
    result = create_appointment(user_id, data['doctor_id'], data['service'], data['date'], data['time'])
    if result:
        await callback.message.edit_text("✅ Запись подтверждена! Вы получите напоминание за 24 часа.")
    else:
        await callback.message.edit_text("❌ Ошибка: слот уже занят. Попробуйте другое время.")
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=main_menu(user[1]))

@dp.callback_query(lambda c: c.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    user = get_user_by_chat_id(callback.message.chat.id)
    role = user[1] if user else 'patient'
    await callback.message.answer("Главное меню:", reply_markup=main_menu(role))

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
        await callback.message.answer("На сегодня записей нет.")
    else:
        text = "📋 Записи на сегодня:\n"
        for r in rows:
            text += f"ID:{r[0]} | {r[1]} -> {r[2]} в {r[3]} (статус: {r[4]})\n"
        await callback.message.answer(text)

@dp.callback_query(lambda c: c.data == "mark_visited_prompt")
async def prompt_mark_visited(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminMarkVisit.waiting_for_id)
    await callback.message.answer("Введите ID записи, которую хотите отметить как посещённую (цифру).")

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

@dp.callback_query(lambda c: c.data == "report_start")
async def report_start(callback: CallbackQuery):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT status FROM appointments WHERE date=?", (today,))
    rows = cur.fetchall()
    conn.close()
    total = len(rows)
    missed = sum(1 for r in rows if r[0] == 'missed')
    rescheduled = sum(1 for r in rows if r[0] == 'rescheduled')
    await callback.message.answer(f"📊 Отчёт за {today}:\nВсего записей: {total}\nНеявок: {missed}\nПереносов: {rescheduled}")

@dp.callback_query(lambda c: c.data == "my_appointments")
async def my_appointments(callback: CallbackQuery):
    user = get_user_by_chat_id(callback.message.chat.id)
    if not user:
        await callback.message.answer("Ошибка: пользователь не найден.")
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
        await callback.message.answer("У вас пока нет записей.")
    else:
        text = "Ваши записи:\n"
        for r in rows:
            text += f"ID:{r[0]} | {r[1]} | {r[2]} в {r[3]} (статус: {r[4]})\n"
        await callback.message.answer(text)

@dp.callback_query(lambda c: c.data == "my_schedule")
async def doctor_schedule(callback: CallbackQuery):
    user = get_user_by_chat_id(callback.message.chat.id)
    if not user or user[1] != 'doctor':
        await callback.message.answer("Доступно только врачам.")
        return
    # Найдём doctor_id по имени врача (упрощённо: можно связать users и doctors)
    # Сейчас допустим, что doctor_id = 1 для демонстрации
    doctor_id = 1
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''SELECT a.time, u.name, a.status
                   FROM appointments a JOIN users u ON a.user_id=u.id
                   WHERE a.doctor_id=? AND a.date=?''', (doctor_id, today))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await callback.message.answer("На сегодня у вас нет записей.")
    else:
        text = f"Ваше расписание на {today}:\n"
        for r in rows:
            text += f"{r[0]} - {r[1]} (статус: {r[2]})\n"
        await callback.message.answer(text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
