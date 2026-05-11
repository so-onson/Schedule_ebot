from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
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

from datetime import timedelta


# ---------- ОТЧЕТ ----------
@router.message(F.text == "📊 Отчет")
async def report_start(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, name
        FROM activities
        WHERE user_id=?
    """, (user_id,))

    rows = cursor.fetchall()

    if not rows:
        await message.answer("Нет активностей")
        return

    buttons = []

    for act_id, name in rows:
        buttons.append([
            InlineKeyboardButton(
                text=name,
                callback_data=f"report_activity_{act_id}"
            )
        ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await message.answer(
        "Выбери активность:",
        reply_markup=keyboard
    )


# ---------- ВЫБОР ПЕРИОДА ----------
@router.callback_query(
    F.data.startswith("report_activity_")
)
async def report_choose_period(
    callback: CallbackQuery
):

    activity_id = int(
        callback.data.replace(
            "report_activity_",
            ""
        )
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сегодня",
                    callback_data=f"period_today_{activity_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="7 дней",
                    callback_data=f"period_7_{activity_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="30 дней",
                    callback_data=f"period_30_{activity_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Все время",
                    callback_data=f"period_all_{activity_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "Выбери период:",
        reply_markup=keyboard
    )


# ---------- ГЕНЕРАЦИЯ ОТЧЕТА ----------
@router.callback_query(
    F.data.startswith("period_")
)
async def report_finish(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    data = callback.data.split("_")

    period = data[1]
    activity_id = int(data[2])

    # получаем активность
    cursor.execute("""
        SELECT name, daily_goal
        FROM activities
        WHERE id=? AND user_id=?
    """, (activity_id, user_id))

    row = cursor.fetchone()

    if not row:
        await callback.message.answer("Ошибка активности")
        return

    activity_name, daily_goal = row

    # определяем период
    now = datetime.now()

    start_date = None

    if period == "today":
        start_date = now.date()

    elif period == "7":
        start_date = (now - timedelta(days=7)).date()

    elif period == "30":
        start_date = (now - timedelta(days=30)).date()

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

        seconds = (
            end_dt - start_dt
        ).total_seconds()

        total_seconds += seconds

        day = str(start_dt.date())

        if day not in days_stats:
            days_stats[day] = 0

        days_stats[day] += seconds

    total_hours = total_seconds / 3600

    avg = 0

    if len(days_stats) > 0:
        avg = total_hours / len(days_stats)

    completed_days = 0

    for sec in days_stats.values():
        if sec / 3600 >= daily_goal:
            completed_days += 1

    text = (
        f"📊 {activity_name}\n\n"
        f"Период: {period}\n"
        f"Всего: {total_hours:.2f} ч\n"
        f"Среднее: {avg:.2f} ч/день\n"
        f"Выполнено дней:\n"
        f"{completed_days}/{len(days_stats)}"
    )

    await callback.message.edit_text(text)
# @router.message(F.text == "📁 Активности")
# async def show_activities(message: Message):
#     await list_activities(message)
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