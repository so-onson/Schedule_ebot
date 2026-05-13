from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command

from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from aiogram.enums import ParseMode

from datetime import datetime, timedelta
from db import cursor, conn

router = Router()

# ---------- КЛАВИАТУРА ----------
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="⚪️ Начать сессию"), 
            KeyboardButton(text="⬛️ Закончить")
        ],
        [KeyboardButton(text="📄 Отчет")],
        [KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="📁 Смена активности")]
    ],
    
    resize_keyboard=True
)

# ---------- FSM ----------
class SetupState(StatesGroup):
    waiting_hours = State()

class ActivityState(StatesGroup):
    waiting_name = State()

class ReminderState(StatesGroup):
    choosing_on_off = State()
    choosing_hours = State()

# ---------- START ----------
@router.message(Command("start"))
async def cmd_start(message: Message):
    buttons = [
        [InlineKeyboardButton(
            text="Добавить активность",
            callback_data="add_activity"
        )],
        [InlineKeyboardButton(
            text="Выбрать активность",
            callback_data="set_activity"
        )]
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

    await message.answer(
        "Я помогу отслеживать твое рабочее время 👀\n\n"
        "Создай новую активность или выбери из существующих",
        reply_markup=keyboard
    )

@router.message(F.text == "Добавить активность")
async def add_activity_start(message: Message, state: FSMContext):
    await message.answer("Введите название новой активности:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(ActivityState.waiting_name)

@router.callback_query(F.data == "add_activity")
async def add_activity_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название новой активности:")
    await state.set_state(ActivityState.waiting_name)
    

@router.message(ActivityState.waiting_name)
async def handle_activity_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text

    cursor.execute("""
        INSERT INTO activity (user_id, name, daily_goal, reminder_hours, reminders_on)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, name, 8, 6, 0))

    cursor.execute("""
        SELECT id FROM activity
        WHERE user_id=? AND name=?
    """, (user_id, name))

    row = cursor.fetchone()

    if not row:
        await message.answer("Ошибка создания")
        return

    activity_id = row[0]

    cursor.execute("""
        INSERT OR REPLACE INTO user_state (user_id, current_activity_id)
        VALUES (?, ?)
    """, (user_id, activity_id))

    conn.commit()

    await message.answer(
        f"Создано: {name} ✔️\n\n"
        "Количество часов по умолчанию: 8\n"
        "Напоминания отключены\n",
        reply_markup=main_keyboard
    )

    await state.clear()

# ---------- НАЧАТЬ РАБОТУ ----------
@router.message(F.text == "⚪️ Начать сессию")
async def start_work(message: Message):
    user_id = message.from_user.id

    cursor.execute("""
        SELECT current_activity_id FROM user_state WHERE user_id=?
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer("Сначала выбери активность через 📁 Активности")
        return

    activity_id = row[0]

    cursor.execute("""
        SELECT name
        FROM activity
        WHERE id=? AND user_id=?
    """, (activity_id, user_id))

    row = cursor.fetchone()

    if not row:
        await message.answer("Ошибка активности")
        return

    activity_name = row[0]
    await message.answer(
        f"Активность <b>{activity_name}</b>", 
        parse_mode=ParseMode.HTML
    )

    cursor.execute("""
        SELECT id FROM act_session
        WHERE activity_id=? AND end_time IS NULL
    """, (activity_id,))

    if cursor.fetchone():
        await message.answer("Сессия уже идёт 😅")
        return

    now = datetime.now().isoformat()
    date = datetime.date(datetime.now()).isoformat()

    cursor.execute("""
        INSERT INTO act_session (activity_id, date, start_time)
        VALUES (?, ?, ?)
    """, (activity_id, date, now))

    conn.commit()

    await message.answer("Старт 🚀")

# ---------- ЗАКОНЧИТЬ ----------
@router.message(F.text == "⬛️ Закончить")
async def stop_work(message: Message):
    user_id = message.from_user.id

    cursor.execute("""
        SELECT current_activity_id FROM user_state WHERE user_id=?
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer("Сначала выбери активность")
        return

    activity_id = row[0]

    cursor.execute("""
        SELECT id, start_time FROM act_session
        WHERE activity_id=? AND end_time IS NULL
        ORDER BY id DESC LIMIT 1
    """, (activity_id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Нет активной сессии ✖️")
        return

    session_id, start_time = row

    now = datetime.now().isoformat()

    cursor.execute("""
        UPDATE act_session
        SET end_time=?
        WHERE id=?
    """, (now, session_id))

    conn.commit()

    duration = (
        datetime.fromisoformat(now) -
        datetime.fromisoformat(start_time)
    )

    await message.answer(f"Отработано: {duration}")

from datetime import timedelta

# ---------- ОТЧЕТ ----------
@router.message(F.text == "📄 Отчет")
async def report_start(message: Message):

    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, name
        FROM activity
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
def format_seconds(seconds: float) -> str:
    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    sec = seconds % 60

    return f"{hours}ч {minutes}м {sec}с"

@router.callback_query(F.data.startswith("period_"))
async def report_finish(callback: CallbackQuery):
    user_id = callback.from_user.id

    _, period, activity_id = callback.data.split("_")
    activity_id = int(activity_id)

    cursor.execute("""
        SELECT name, daily_goal
        FROM activity
        WHERE id=? AND user_id=?
    """, (activity_id, user_id))

    row = cursor.fetchone()

    if not row:
        await callback.message.edit_text("Ошибка активности")
        return

    activity_name, daily_goal = row

    now = datetime.now()

    if period == "today":
        start_date = now.date()

    elif period == "7":
        start_date = (now - timedelta(days=7)).date()

    elif period == "30":
        start_date = (now - timedelta(days=30)).date()

    else:
        start_date = None  # all time

    cursor.execute("""
        SELECT start_time, end_time
        FROM act_session
        WHERE activity_id=?
        AND end_time IS NOT NULL
    """, (activity_id,))

    rows = cursor.fetchall()

    total_seconds = 0
    days_stats = {}

    for start, end in rows:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)

        if start_date and start_dt.date() < start_date:
            continue

        seconds = (end_dt - start_dt).total_seconds()

        total_seconds += seconds

        day = str(start_dt.date())
        days_stats[day] = days_stats.get(day, 0) + seconds

    total_hours = total_seconds / 3600
    avg = total_seconds / len(days_stats) if days_stats else 0

    text_lines = [
        f"<b>{activity_name}</b>",
        f"📓 Период: {period}",
        "",
        "По дням:"
    ]

    for day, sec in sorted(days_stats.items()):
        status = "✔️" if sec / 3600 >= daily_goal else ""

        text_lines.append(
            f"{day} — {format_seconds(sec)} {status}"
        )

    text_lines += [
        "",
        f"⏱ Всего: {format_seconds(total_seconds)}",
        f"↗ Среднее: {format_seconds(avg)}",
        f"☑ Норма: {daily_goal} ч"
    ]

    await callback.message.edit_text(
        "\n".join(text_lines),
        parse_mode=ParseMode.HTML
    )

# ---------- СМЕНА АКТИВНОСТИ ----------  
@router.callback_query(F.data == "set_activity")
async def set_activity_start(callback: CallbackQuery):
    user_id = callback.from_user.id

    cursor.execute("""
        SELECT id, name FROM activity WHERE user_id=?
    """, (user_id,))

    rows = cursor.fetchall()

    if not rows:
        await callback.message.answer("Нет активностей. Необходимо добавить")
        return

    buttons = []
    for act_id, name in rows:
        buttons.append([KeyboardButton(text=f"📌 {name}")])

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    await callback.message.answer(
        "Выбери активность: ",
        reply_markup=keyboard
    )

@router.message(F.text == "📁 Смена активности")
async def show_activities(message: Message):
    user_id = message.from_user.id

    cursor.execute("""
        SELECT id, name FROM activity WHERE user_id=?
    """, (user_id,))

    rows = cursor.fetchall()

    if not rows:
        await message.answer("Нет активностей. Необходимо добавить")
        return

    buttons = []
    for id, name in rows:
        buttons.append([KeyboardButton(text=f"📌 {name}")])

    buttons.append([KeyboardButton(text="Назад")])

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    await message.answer(
        f"Текущая активность: <b>{name}</b>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@router.message(F.text.startswith("📌 "))
async def select_activity_button(message: Message):
    user_id = message.from_user.id

    name = message.text.replace("📌 ", "")

    cursor.execute("""
        SELECT id FROM activity
        WHERE user_id=? AND name=?
    """, (user_id, name))

    row = cursor.fetchone()

    if not row:
        await message.answer("Ошибка выбора")
        return

    activity_id = row[0]

    cursor.execute("""
        INSERT OR REPLACE INTO user_state (user_id, current_activity_id)
        VALUES (?, ?)
    """, (user_id, activity_id))

    conn.commit()

    await message.answer(
        f"Выбрано: {name} ✔️",
        reply_markup=main_keyboard
    )

# ---------- НАСТРОЙКИ ----------
@router.message(F.text == "⚙️ Настройки")
async def setup(message: Message):
    user_id = message.from_user.id

    buttons = [
        [KeyboardButton(text="Изменить цель по ч/д")],
        [KeyboardButton(text="Настроить напоминания")],
        [KeyboardButton(text="Добавить активность")],
        [KeyboardButton(text="Назад")]
    ]

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    cursor.execute("""
        SELECT current_activity_id FROM user_state WHERE user_id=?
    """, (user_id,))
    row = cursor.fetchone()

    if not row:
        await message.answer("Сначала выбери активность через 📁 Смена активности")
        return

    activity_id = row[0]

    cursor.execute("""
        SELECT name
        FROM activity
        WHERE id=? AND user_id=?
    """, (activity_id, user_id))

    row = cursor.fetchone()

    if not row:
        await message.answer("Ошибка активности")
        return

    activity_name = row[0]

    await message.answer(
        f"Настройки активности: <b>{activity_name}</b>",
        reply_markup=keyboard, 
        parse_mode=ParseMode.HTML
    )

@router.message(F.text == "Изменить цель по ч/д")
async def setup(message: Message, state: FSMContext):
    await message.answer("Сколько часов в день ты планируешь работать?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(SetupState.waiting_hours)


@router.message(SetupState.waiting_hours)
async def process_hours(message: Message, state: FSMContext):
    user_id = message.from_user.id

    try:
        hours = float(message.text)
    except:
        await message.answer(
            "Введи число (например 6.5)"
        )
        return

    cursor.execute("""
        SELECT current_activity_id
        FROM user_state
        WHERE user_id=?
    """, (user_id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Активность не выбрана")
        return

    activity_id = row[0]

    cursor.execute("""
        UPDATE activity
        SET daily_goal=?
        WHERE id=?
    """, (hours, activity_id))

    conn.commit()

    await message.answer(
        f"Цель обновлена: {hours} ч/д ✔️",
        reply_markup=main_keyboard
    )

    await state.clear()

@router.message(F.text == "Настроить напоминания")
async def setup_reminders(message: Message, state: FSMContext):

    buttons = [
        [
            KeyboardButton(text="Включить"),
            KeyboardButton(text="Выключить")
        ],
        [KeyboardButton(text="Изменить интервал")],
        [KeyboardButton(text="Назад")]
    ]

    keyboard = ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
    )

    await message.answer(
        "Настрой напоминания:",
        reply_markup=keyboard
    )

    await state.set_state(ReminderState.choosing_on_off)

@router.message(ReminderState.choosing_on_off)
async def handle_reminders_toggle(message: Message, state: FSMContext):

    user_id = message.from_user.id
    text = message.text

    cursor.execute("""
        SELECT current_activity_id
        FROM user_state
        WHERE user_id=?
    """, (user_id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Сначала выбери активность")
        return

    activity_id = row[0]

    if text == "Включить":
        cursor.execute("""
            UPDATE activity
            SET reminders_on=1
            WHERE id=?
        """, (activity_id,))

        conn.commit()

        await message.answer("Напоминания включены ✔️")

    elif text == "Выключить":
        cursor.execute("""
            UPDATE activity
            SET reminders_on=0
            WHERE id=?
        """, (activity_id,))

        conn.commit()

        await message.answer("Напоминания выключены ✖️")

    elif text == "Изменить интервал":

        await message.answer(
            "Через сколько часов напоминать?", 
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(ReminderState.choosing_hours)
        return
    
    elif text == "Назад":
        await state.clear()

        await message.answer(
            "...",
            reply_markup=main_keyboard
        )

    await state.clear()

@router.message(ReminderState.choosing_hours)
async def set_reminder_hours(message: Message, state: FSMContext):

    user_id = message.from_user.id

    try:
        hours = float(message.text)
    except:
        await message.answer(
            "Введите число (например 6.5)",
            reply_markup=main_keyboard
        )
        return

    cursor.execute("""
        SELECT current_activity_id
        FROM user_state
        WHERE user_id=?
    """, (user_id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Сначала выбери активность")
        return

    activity_id = row[0]

    cursor.execute("""
        UPDATE activity
        SET reminder_hours=?
        WHERE id=?
    """, (hours, activity_id))

    conn.commit()

    await message.answer(
        f"Интервал установлен: {hours} ч ⏰",
        reply_markup=main_keyboard
    )

    await state.clear()

@router.message(F.text == "Назад")
async def setup(message: Message):
    await message.answer("...", reply_markup=main_keyboard)