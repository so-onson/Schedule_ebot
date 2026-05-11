from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from datetime import datetime
from db import cursor, conn

router = Router()

# ---------- КЛАВИАТУРА ----------
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="▶️ Начать работу")],
        [KeyboardButton(text="⏹ Закончить работу")],
        [KeyboardButton(text="📊 Отчет")],
        [KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="📁 Активности")],
        [KeyboardButton(text="Добавить активность")]
    ],
    
    resize_keyboard=True
)

# ---------- FSM ----------
class SetupState(StatesGroup):
    waiting_hours = State()

class ActivityState(StatesGroup):
    waiting_name = State()


# ---------- START ----------
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Я помогу отслеживать твое рабочее время 👀",
        reply_markup=main_keyboard
    )

@router.message(F.text == "📁 Активности")
async def show_activities(message: Message):
    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, name FROM activities WHERE user_id=?
    """, (user_id,))

    rows = cursor.fetchall()

    if not rows:
        await message.answer("Нет активностей. Создай через /add")
        return

    # создаём кнопки
    buttons = []
    for act_id, name in rows:
        buttons.append([KeyboardButton(text=f"📌 {name}")])

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    await message.answer(
    f"lol Выбрано: {name} ✅",
    reply_markup=keyboard
)

@router.message(F.text.startswith("📌 "))
async def select_activity_button(message: Message):
    user_id = message.from_user.id

    # достаём название
    name = message.text.replace("📌 ", "")

    # ищем в БД
    cursor.execute("""
        SELECT id FROM activities
        WHERE user_id=? AND name=?
    """, (user_id, name))

    row = cursor.fetchone()

    if not row:
        await message.answer("Ошибка выбора")
        return

    activity_id = row[0]

    # сохраняем выбор
    cursor.execute("""
        INSERT OR REPLACE INTO user_state (user_id, current_activity_id)
        VALUES (?, ?)
    """, (user_id, activity_id))

    conn.commit()

    await message.answer(
    f"Выбрано: {name} ✅",
    reply_markup=main_keyboard)


@router.message(F.text == "Добавить активность")
async def add_activity_start(message: Message, state: FSMContext):
    await message.answer("Введите название новой активности:")
    await state.set_state(ActivityState.waiting_name)
    

@router.message(ActivityState.waiting_name)
async def handle_activity_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text

    cursor.execute("""
        INSERT INTO activities (user_id, name, daily_goal, reminder_hours, reminders_on)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, name, 8, 6, 1))

    conn.commit()

    await message.answer(
        f"Создано: {name} ✅",
        reply_markup=main_keyboard
    )

    await state.clear()

@router.message(Command("select"))
async def select_activity(message: Message):
    user_id = message.from_user.id

    try:
        act_id = int(message.text.split()[1])
    except:
        await message.answer("Используй: /select ID")
        return

    # проверяем, что такая активность есть
    cursor.execute("""
        SELECT id FROM activities WHERE id=? AND user_id=?
    """, (act_id, user_id))

    if not cursor.fetchone():
        await message.answer("Нет такой активности")
        return

    # сохраняем выбор
    cursor.execute("""
        INSERT OR REPLACE INTO user_state (user_id, current_activity_id)
        VALUES (?, ?)
    """, (user_id, act_id))

    conn.commit()

    await message.answer("Активность выбрана ✅")

# ---------- НАЧАТЬ РАБОТУ ----------
@router.message(F.text == "▶️ Начать работу")
async def start_work(message: Message):
    user_id = message.from_user.id

    # 1. Получаем выбранную активность
    cursor.execute("""
        SELECT current_activity_id FROM user_state WHERE user_id=?
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer("Сначала выбери активность через 📁 Активности")
        return

    activity_id = row[0]
    await message.answer(f"Активность {activity_id}")

    # 2. Проверяем: нет ли уже активной сессии
    cursor.execute("""
        SELECT id FROM work_sessions
        WHERE activity_id=? AND end_time IS NULL
    """, (activity_id,))

    if cursor.fetchone():
        await message.answer("Сессия уже идёт 😅")
        return

    # 3. Создаём новую сессию
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO work_sessions (activity_id, start_time)
        VALUES (?, ?)
    """, (activity_id, now))

    conn.commit()

    await message.answer("Старт 🚀")

# ---------- ЗАКОНЧИТЬ ----------
@router.message(F.text == "⏹ Закончить работу")
async def stop_work(message: Message):
    user_id = message.from_user.id

    # 1. Получаем выбранную активность
    cursor.execute("""
        SELECT current_activity_id FROM user_state WHERE user_id=?
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer("Сначала выбери активность")
        return

    activity_id = row[0]

    # 2. Находим последнюю активную сессию
    cursor.execute("""
        SELECT id, start_time FROM work_sessions
        WHERE activity_id=? AND end_time IS NULL
        ORDER BY id DESC LIMIT 1
    """, (activity_id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Нет активной сессии 🤷‍♀️")
        return

    session_id, start_time = row

    # 3. Завершаем её
    now = datetime.now().isoformat()

    cursor.execute("""
        UPDATE work_sessions
        SET end_time=?
        WHERE id=?
    """, (now, session_id))

    conn.commit()

    # 4. Считаем длительность
    duration = (
        datetime.fromisoformat(now) -
        datetime.fromisoformat(start_time)
    )

    await message.answer(f"Отработано: {duration}")

class ReportState(StatesGroup):
    choosing_activity = State()
    choosing_period = State()

# ---------- ОТЧЕТ ----------
@router.message(F.text == "📊 Отчет")
async def report_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    cursor.execute("""
        SELECT name FROM activities
        WHERE user_id=?
    """, (user_id,))

    rows = cursor.fetchall()

    if not rows:
        await message.answer("Нет активностей")
        return

    buttons = [
        [KeyboardButton(text=f"📌 {name}")]
        for (name,) in rows
    ]

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    await message.answer(
        "Выбери активность:",
        reply_markup=keyboard
    )

    await state.set_state(ReportState.choosing_activity)


@router.message(ReportState.choosing_activity)
async def report_choose_activity(
    message: Message,
    state: FSMContext
):
    activity_name = message.text.replace("📌 ", "")

    await state.update_data(activity_name=activity_name)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сегодня")],
            [KeyboardButton(text="7 дней")],
            [KeyboardButton(text="30 дней")],
            [KeyboardButton(text="Все время")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        "Выбери период:",
        reply_markup=keyboard
    )

    await state.set_state(ReportState.choosing_period)


from datetime import timedelta

@router.message(ReportState.choosing_period)
async def report_finish(
    message: Message,
    state: FSMContext
):
    user_id = message.from_user.id
    period_text = message.text

    data = await state.get_data()
    activity_name = data["activity_name"]

    # получаем activity_id
    cursor.execute("""
        SELECT id, daily_goal
        FROM activities
        WHERE user_id=? AND name=?
    """, (user_id, activity_name))

    row = cursor.fetchone()

    if not row:
        await message.answer("Ошибка активности")
        return

    activity_id, daily_goal = row

    # определяем период
    now = datetime.now()

    if period_text == "Сегодня":
        start_date = now.date()

    elif period_text == "7 дней":
        start_date = (now - timedelta(days=7)).date()

    elif period_text == "30 дней":
        start_date = (now - timedelta(days=30)).date()

    else:
        start_date = None

    # загружаем сессии
    cursor.execute("""
        SELECT start_time, end_time
        FROM work_sessions
        WHERE activity_id=?
        AND end_time IS NOT NULL
    """, (activity_id,))

    rows = cursor.fetchall()

    total_seconds = 0
    days_stats = {}

    for start, end in rows:

        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        # фильтр периода
        if start_date:
            if start_dt.date() < start_date:
                continue

        seconds = (end_dt - start_dt).total_seconds()

        total_seconds += seconds

        day = str(start_dt.date())

        if day not in days_stats:
            days_stats[day] = 0

        days_stats[day] += seconds

    total_hours = total_seconds / 3600

    # считаем выполненные дни
    completed_days = 0

    for sec in days_stats.values():
        if sec / 3600 >= daily_goal:
            completed_days += 1

    avg = 0

    if len(days_stats) > 0:
        avg = total_hours / len(days_stats)

    text = (
        f"📊 {activity_name}\n"
        f"Период: {period_text}\n\n"
        f"Всего: {total_hours:.2f} ч\n"
        f"Среднее: {avg:.2f} ч/день\n"
        f"Дней с выполненной нормой: "
        f"{completed_days}/{len(days_stats)}"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard
    )

    await state.clear()
# @router.message(F.text == "📁 Активности")
# async def show_activities(message: Message):
#     await list_activities(message)

# ---------- НАСТРОЙКИ ----------
@router.message(F.text == "⚙️ Настройки")
async def setup(message: Message, state: FSMContext):
    await message.answer("Сколько часов в день ты планируешь работать?")
    await state.set_state(SetupState.waiting_hours)


@router.message(SetupState.waiting_hours)
async def process_hours(message: Message, state: FSMContext):
    user_id = message.from_user.id

    try:
        hours = float(message.text)
    except:
        await message.answer("Введи число (например 6 или 8)")
        return

    cursor.execute("""
        INSERT OR REPLACE INTO work_settings (user_id, hours_per_day)
        VALUES (?, ?)
    """, (user_id, hours))

    conn.commit()

    await message.answer(f"Сохранила: {hours} часов 👍")
    await state.clear()