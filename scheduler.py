from datetime import datetime, timedelta
from db import cursor

async def check_sessions(bot):
    cursor.execute("""
        SELECT act_s.start_time, act_s.activity_id, a.user_id, a.name, a.reminder_hours, a.reminders_on
        FROM act_session act_s
        JOIN activity a ON act_s.activity_id = a.id
        WHERE act_s.end_time IS NULL
    """)

    rows = cursor.fetchall()

    for start_time, activity_id, user_id, name, reminder_hours, reminders_on in rows:

        if not reminders_on:
            continue

        start_dt = datetime.fromisoformat(start_time)

        if datetime.now() - start_dt > timedelta(hours=reminder_hours):
            await bot.send_message(
                user_id,
                f"⏰ Не забудь завершить: {name}"
            )