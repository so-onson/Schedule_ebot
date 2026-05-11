from datetime import datetime, timedelta
from db import cursor

async def check_sessions(bot):
    cursor.execute("""
        SELECT ws.start_time, ws.activity_id, a.user_id, a.reminder_hours, a.reminders_on
        FROM work_sessions ws
        JOIN activities a ON ws.activity_id = a.id
        WHERE ws.end_time IS NULL
    """)

    rows = cursor.fetchall()

    for start_time, activity_id, user_id, reminder_hours, reminders_on in rows:

        if not reminders_on:
            continue

        start_dt = datetime.fromisoformat(start_time)

        if datetime.now() - start_dt > timedelta(hours=reminder_hours):
            await bot.send_message(
                user_id,
                "Ты не забыла закончить сессию? ⏰"
            )