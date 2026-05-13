import sqlite3

conn = sqlite3.connect("schedule_tracker.db")
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_state (
    user_id INTEGER PRIMARY KEY,
    current_activity_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        daily_goal REAL,
        reminder_hours REAL,
        reminders_on INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS act_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id INTEGER,
        date TEXT,
        start_time TEXT,
        end_time TEXT
    )
    """)

    conn.commit()