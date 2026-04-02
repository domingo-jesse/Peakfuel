import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import random
from typing import Any

import pandas as pd

DB_PATH = "peakfuel.db"


TROPHY_DEFINITIONS = [
    {"code": "first_workout", "name": "First Workout", "emoji": "🏋️", "description": "Log your first workout."},
    {"code": "first_hike", "name": "First Hike", "emoji": "🥾", "description": "Log your first hike."},
    {"code": "first_meal", "name": "First Meal Logged", "emoji": "🍽️", "description": "Log your first food entry."},
    {"code": "streak_3", "name": "3 Day Logging Streak", "emoji": "🔥", "description": "Log something 3 days in a row."},
    {"code": "streak_7", "name": "7 Day Logging Streak", "emoji": "🔥", "description": "Log something 7 days in a row."},
    {"code": "weekend_warrior", "name": "Weekend Warrior", "emoji": "🏅", "description": "Log activity on both Saturday and Sunday."},
    {"code": "mountain_goat", "name": "Mountain Goat", "emoji": "⛰️", "description": "Hike 25 total miles."},
    {"code": "summit_chaser", "name": "Summit Chaser", "emoji": "🧗", "description": "Gain 5000 ft elevation from hikes."},
    {"code": "iron_will", "name": "Iron Will", "emoji": "💪", "description": "Complete 10 workouts."},
    {"code": "protein_hero", "name": "Protein Hero", "emoji": "🥩", "description": "Hit protein goal 5 times."},
    {"code": "consistency_king", "name": "Consistency King", "emoji": "👑", "description": "Log something 14 days in a row."},
    {"code": "cardio_cat", "name": "Cardio Cat", "emoji": "🐆", "description": "Complete 5 hikes."},
    {"code": "gym_rat", "name": "Gym Rat", "emoji": "🐀", "description": "Complete 25 workouts."},
]


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    workout_name TEXT,
    muscle_group TEXT,
    duration_minutes INTEGER,
    cardio_minutes INTEGER,
    notes TEXT,
    original_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL,
    exercise_name TEXT,
    sets INTEGER,
    reps INTEGER,
    weight REAL,
    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    trail_name TEXT,
    distance_miles REAL,
    duration_minutes INTEGER,
    elevation_gain_ft INTEGER,
    difficulty TEXT,
    notes TEXT,
    original_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS foods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    meal_type TEXT,
    total_calories REAL,
    total_protein REAL,
    total_carbs REAL,
    total_fat REAL,
    notes TEXT,
    original_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS food_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food_id INTEGER NOT NULL,
    item_name TEXT,
    estimated_calories REAL,
    protein_g REAL,
    carbs_g REAL,
    fat_g REAL,
    FOREIGN KEY (food_id) REFERENCES foods(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trophies (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    emoji TEXT,
    unlocked INTEGER DEFAULT 0,
    unlocked_date TEXT,
    progress REAL DEFAULT 0,
    target REAL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    calorie_goal REAL DEFAULT 2400,
    protein_goal REAL DEFAULT 160,
    weekly_workout_goal INTEGER DEFAULT 4,
    weekly_hike_goal INTEGER DEFAULT 2
);

CREATE TABLE IF NOT EXISTS entry_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    raw_text TEXT NOT NULL,
    parsed_type TEXT,
    confidence REAL DEFAULT 0,
    status TEXT DEFAULT 'pending',
    payload_json TEXT,
    target_table TEXT,
    target_id INTEGER
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(get_conn()) as conn:
        conn.executescript(SCHEMA_SQL)
        for trophy in TROPHY_DEFINITIONS:
            conn.execute(
                """
                INSERT OR IGNORE INTO trophies(code, name, description, emoji, target)
                VALUES (?, ?, ?, ?, ?)
                """,
                (trophy["code"], trophy["name"], trophy["description"], trophy["emoji"], _target_for_code(trophy["code"])),
            )
        conn.execute("INSERT OR IGNORE INTO profile(id) VALUES (1)")
        conn.commit()


def _target_for_code(code: str) -> float:
    return {
        "streak_3": 3,
        "streak_7": 7,
        "consistency_king": 14,
        "mountain_goat": 25,
        "summit_chaser": 5000,
        "iron_will": 10,
        "protein_hero": 5,
        "cardio_cat": 5,
        "gym_rat": 25,
    }.get(code, 1)


def insert_workout(payload: dict[str, Any]) -> int:
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            INSERT INTO workouts(date, workout_name, muscle_group, duration_minutes, cardio_minutes, notes, original_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("date", str(date.today())),
                payload.get("workout_name"),
                payload.get("muscle_group"),
                payload.get("duration_minutes"),
                payload.get("cardio_minutes"),
                payload.get("notes"),
                payload.get("original_text"),
            ),
        )
        workout_id = cur.lastrowid
        for ex in payload.get("exercises", []):
            conn.execute(
                """
                INSERT INTO workout_exercises(workout_id, exercise_name, sets, reps, weight)
                VALUES (?, ?, ?, ?, ?)
                """,
                (workout_id, ex.get("exercise_name"), ex.get("sets"), ex.get("reps"), ex.get("weight")),
            )
        conn.commit()
    refresh_trophies()
    return workout_id


def insert_hike(payload: dict[str, Any]) -> int:
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            INSERT INTO hikes(date, trail_name, distance_miles, duration_minutes, elevation_gain_ft, difficulty, notes, original_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("date", str(date.today())),
                payload.get("trail_name"),
                payload.get("distance_miles"),
                payload.get("duration_minutes"),
                payload.get("elevation_gain_ft"),
                payload.get("difficulty"),
                payload.get("notes"),
                payload.get("original_text"),
            ),
        )
        conn.commit()
    refresh_trophies()
    return cur.lastrowid


def insert_food(payload: dict[str, Any]) -> int:
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            INSERT INTO foods(date, meal_type, total_calories, total_protein, total_carbs, total_fat, notes, original_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("date", str(date.today())),
                payload.get("meal_type"),
                payload.get("total_calories"),
                payload.get("total_protein"),
                payload.get("total_carbs"),
                payload.get("total_fat"),
                payload.get("notes"),
                payload.get("original_text"),
            ),
        )
        food_id = cur.lastrowid
        for item in payload.get("foods", []):
            conn.execute(
                """
                INSERT INTO food_items(food_id, item_name, estimated_calories, protein_g, carbs_g, fat_g)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (food_id, item.get("item_name"), item.get("estimated_calories"), item.get("protein_g"), item.get("carbs_g"), item.get("fat_g")),
            )
        conn.commit()
    refresh_trophies()
    return food_id


def delete_entry(table: str, row_id: int) -> None:
    allowed = {"workouts", "hikes", "foods"}
    if table not in allowed:
        return
    with closing(get_conn()) as conn:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        conn.commit()
    refresh_trophies()


def read_df(query: str, params: tuple = ()) -> pd.DataFrame:
    with closing(get_conn()) as conn:
        return pd.read_sql_query(query, conn, params=params)


def fetch_workouts() -> pd.DataFrame:
    return read_df("SELECT * FROM workouts ORDER BY date DESC, id DESC")


def fetch_hikes() -> pd.DataFrame:
    return read_df("SELECT * FROM hikes ORDER BY date DESC, id DESC")


def fetch_foods() -> pd.DataFrame:
    return read_df("SELECT * FROM foods ORDER BY date DESC, id DESC")


def fetch_exercises(workout_id: int) -> pd.DataFrame:
    return read_df("SELECT * FROM workout_exercises WHERE workout_id = ?", (workout_id,))


def fetch_food_items(food_id: int) -> pd.DataFrame:
    return read_df("SELECT * FROM food_items WHERE food_id = ?", (food_id,))


def fetch_profile() -> dict[str, Any]:
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        return dict(row) if row else {}


def update_profile(payload: dict[str, Any]) -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            """
            UPDATE profile
            SET calorie_goal = ?, protein_goal = ?, weekly_workout_goal = ?, weekly_hike_goal = ?
            WHERE id = 1
            """,
            (
                payload.get("calorie_goal", 2400),
                payload.get("protein_goal", 160),
                payload.get("weekly_workout_goal", 4),
                payload.get("weekly_hike_goal", 2),
            ),
        )
        conn.commit()


def insert_history_entry(raw_text: str, parsed_type: str, confidence: float, payload_json: str) -> int:
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """
            INSERT INTO entry_history(raw_text, parsed_type, confidence, status, payload_json)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (raw_text, parsed_type, confidence, payload_json),
        )
        conn.commit()
        return cur.lastrowid


def fetch_history_entries(status: str | None = None) -> pd.DataFrame:
    if status:
        return read_df("SELECT * FROM entry_history WHERE status = ? ORDER BY id DESC", (status,))
    return read_df("SELECT * FROM entry_history ORDER BY id DESC")


def update_history_entry(entry_id: int, parsed_type: str, payload_json: str) -> None:
    with closing(get_conn()) as conn:
        conn.execute(
            """
            UPDATE entry_history
            SET parsed_type = ?, payload_json = ?
            WHERE id = ?
            """,
            (parsed_type, payload_json, entry_id),
        )
        conn.commit()


def set_history_status(entry_id: int, status: str) -> None:
    with closing(get_conn()) as conn:
        conn.execute("UPDATE entry_history SET status = ? WHERE id = ?", (status, entry_id))
        conn.commit()


def delete_history_entry(entry_id: int) -> None:
    with closing(get_conn()) as conn:
        conn.execute("DELETE FROM entry_history WHERE id = ?", (entry_id,))
        conn.commit()


def approve_history_entry(entry_id: int, parsed_type: str, payload: dict[str, Any]) -> bool:
    table = None
    target_id = None
    if parsed_type == "workout":
        target_id = insert_workout(payload)
        table = "workouts"
    elif parsed_type == "hike":
        target_id = insert_hike(payload)
        table = "hikes"
    elif parsed_type == "food":
        target_id = insert_food(payload)
        table = "foods"
    else:
        return False

    with closing(get_conn()) as conn:
        conn.execute(
            """
            UPDATE entry_history
            SET status = 'approved', target_table = ?, target_id = ?, parsed_type = ?, payload_json = ?
            WHERE id = ?
            """,
            (table, target_id, parsed_type, json.dumps(payload), entry_id),
        )
        conn.commit()
    return True


def fetch_trophies() -> pd.DataFrame:
    return read_df("SELECT * FROM trophies ORDER BY unlocked DESC, unlocked_date DESC, name")


def _date_set_from_logs() -> set[str]:
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """
            SELECT date FROM workouts
            UNION SELECT date FROM hikes
            UNION SELECT date FROM foods
            """
        ).fetchall()
    return {r[0] for r in rows}


def compute_streaks() -> dict[str, int]:
    dates = sorted(_date_set_from_logs())
    if not dates:
        return {"current": 0, "longest": 0, "days_this_month": 0, "weekly_consistency": 0}

    day_set = {datetime.fromisoformat(d).date() for d in dates}
    today = date.today()
    current = 0
    cursor = today
    while cursor in day_set:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    run = 0
    prev = None
    for d in sorted(day_set):
        if prev and d == prev + timedelta(days=1):
            run += 1
        else:
            run = 1
        longest = max(longest, run)
        prev = d

    month_days = sum(1 for d in day_set if d.month == today.month and d.year == today.year)
    week_days = sum(1 for i in range(7) if (today - timedelta(days=i)) in day_set)
    return {"current": current, "longest": longest, "days_this_month": month_days, "weekly_consistency": week_days}


def refresh_trophies() -> None:
    workouts = fetch_workouts()
    hikes = fetch_hikes()
    foods = fetch_foods()
    profile = fetch_profile()
    streaks = compute_streaks()

    workout_count = len(workouts)
    hike_count = len(hikes)
    meal_count = len(foods)
    total_miles = float(hikes["distance_miles"].fillna(0).sum()) if not hikes.empty else 0
    total_elev = float(hikes["elevation_gain_ft"].fillna(0).sum()) if not hikes.empty else 0
    protein_hits = int((foods["total_protein"].fillna(0) >= profile.get("protein_goal", 160)).sum()) if not foods.empty else 0

    weekend = False
    all_dates = _date_set_from_logs()
    parsed = {datetime.fromisoformat(d).date() for d in all_dates}
    for d in parsed:
        if d.weekday() == 5 and d + timedelta(days=1) in parsed:
            weekend = True
            break

    progress = {
        "first_workout": workout_count,
        "first_hike": hike_count,
        "first_meal": meal_count,
        "streak_3": streaks["current"],
        "streak_7": streaks["current"],
        "weekend_warrior": 1 if weekend else 0,
        "mountain_goat": total_miles,
        "summit_chaser": total_elev,
        "iron_will": workout_count,
        "protein_hero": protein_hits,
        "consistency_king": streaks["current"],
        "cardio_cat": hike_count,
        "gym_rat": workout_count,
    }

    with closing(get_conn()) as conn:
        trophies = conn.execute("SELECT code, unlocked, target FROM trophies").fetchall()
        for row in trophies:
            code = row["code"]
            target = row["target"]
            p = progress.get(code, 0)
            unlocked = 1 if p >= target else 0
            if unlocked and not row["unlocked"]:
                conn.execute(
                    "UPDATE trophies SET unlocked = 1, unlocked_date = ?, progress = ? WHERE code = ?",
                    (str(date.today()), p, code),
                )
            else:
                conn.execute("UPDATE trophies SET progress = ?, unlocked = ? WHERE code = ?", (p, unlocked, code))
        conn.commit()


def seed_demo_data() -> None:
    if not fetch_workouts().empty or not fetch_hikes().empty or not fetch_foods().empty:
        return

    random.seed(42)
    muscles = ["chest", "back", "legs", "shoulders", "full body", "arms"]
    exercises = {
        "chest": ["Bench Press", "Incline Dumbbell Press", "Cable Fly"],
        "back": ["Barbell Row", "Lat Pulldown", "Seated Row"],
        "legs": ["Back Squat", "Leg Press", "Romanian Deadlift"],
        "shoulders": ["Overhead Press", "Lateral Raise", "Rear Delt Fly"],
        "full body": ["Deadlift", "Pull-up", "Kettlebell Swing"],
        "arms": ["Barbell Curl", "Triceps Pushdown", "Hammer Curl"],
    }

    meal_pool = [
        ["Greek yogurt", 180, 17, 20, 3],
        ["Protein shake", 220, 30, 8, 4],
        ["Turkey sandwich", 430, 32, 45, 12],
        ["Chicken bowl", 610, 45, 55, 20],
        ["Eggs + toast", 390, 22, 26, 18],
        ["Salmon + rice", 540, 38, 50, 17],
    ]

    for i in range(20):
        d = date.today() - timedelta(days=random.randint(0, 50))
        mg = random.choice(muscles)
        exs = []
        for ex in random.sample(exercises[mg], 2):
            exs.append({
                "exercise_name": ex,
                "sets": random.randint(3, 5),
                "reps": random.choice([6, 8, 10, 12]),
                "weight": random.choice([65, 95, 115, 135, 155, 185]),
            })
        insert_workout({
            "date": str(d),
            "workout_name": f"{mg.title()} Day",
            "muscle_group": mg,
            "duration_minutes": random.randint(45, 80),
            "cardio_minutes": random.choice([0, 10, 20]),
            "notes": "Strong session.",
            "exercises": exs,
        })

    trails = ["Ridge Loop", "Eagle Peak", "Pine Canyon", "Sunset Trail", "Granite Pass"]
    for i in range(12):
        d = date.today() - timedelta(days=random.randint(0, 60))
        dist = round(random.uniform(2.5, 8.5), 1)
        insert_hike({
            "date": str(d),
            "trail_name": random.choice(trails),
            "distance_miles": dist,
            "duration_minutes": int(dist * random.uniform(20, 33)),
            "elevation_gain_ft": random.randint(300, 1400),
            "difficulty": random.choice(["Easy", "Moderate", "Hard"]),
            "notes": "Great weather and pace.",
        })

    for i in range(30):
        d = date.today() - timedelta(days=random.randint(0, 45))
        meal_type = random.choice(["breakfast", "lunch", "dinner", "snack"])
        items = []
        total_cals = total_p = total_c = total_f = 0
        for x in random.sample(meal_pool, random.randint(1, 3)):
            items.append({
                "item_name": x[0],
                "estimated_calories": x[1],
                "protein_g": x[2],
                "carbs_g": x[3],
                "fat_g": x[4],
            })
            total_cals += x[1]
            total_p += x[2]
            total_c += x[3]
            total_f += x[4]
        insert_food({
            "date": str(d),
            "meal_type": meal_type,
            "foods": items,
            "total_calories": total_cals,
            "total_protein": total_p,
            "total_carbs": total_c,
            "total_fat": total_f,
            "notes": "Auto-seeded demo meal",
        })

    refresh_trophies()
