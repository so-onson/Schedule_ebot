import sqlite3

conn = sqlite3.connect("schedule_tracker.db")
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        daily_goal REAL,
        reminder_hours REAL,
        reminders_on INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS work_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_id INTEGER,
        start_time TEXT,
        end_time TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_state (
    user_id INTEGER PRIMARY KEY,
    current_activity_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS work_settings (
    user_id INTEGER PRIMARY KEY,
    hours_per_day REAL
    )
    """)

    conn.commit()