from dotenv import load_dotenv
from datetime import date

import pandas as pd
import streamlit as st

from ai_parser import parse_entry
from db import (
    compute_streaks,
    delete_entry,
    fetch_exercises,
    fetch_food_items,
    fetch_foods,
    fetch_hikes,
    fetch_profile,
    fetch_trophies,
    fetch_workouts,
    init_db,
    insert_food,
    insert_hike,
    insert_workout,
    refresh_trophies,
    seed_demo_data,
    update_profile,
)
from utils import apply_theme, metric_card, plot_bar, plot_line, plot_pie, safe_dt, week_bounds


load_dotenv()
st.set_page_config(page_title="PeakFuel", page_icon="🏔️", layout="wide")
init_db()

if "seeded" not in st.session_state:
    seed_demo_data()
    st.session_state.seeded = True

apply_theme()

st.title("🏔️ PeakFuel")
st.caption("AI-powered fitness logging with voice + natural language parsing.")

nav = st.sidebar.radio(
    "Navigate",
    [
        "Dashboard",
        "Log Entry",
        "Workout History",
        "Hike History",
        "Food History",
        "Progress & Stats",
        "Trophies / Awards",
    ],
)


if nav == "Log Entry":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Last Submit")
    p = st.session_state.get("last_submit")
    if p:
        st.sidebar.write(f"Type: **{p.get('type', 'unknown')}**")
        st.sidebar.write(f"Confidence: **{round(float(p.get('confidence', 0))*100)}%**")


def save_payload(entry_type: str, payload: dict):
    if entry_type == "workout":
        insert_workout(payload)
    elif entry_type == "hike":
        insert_hike(payload)
    elif entry_type == "food":
        insert_food(payload)
    else:
        st.warning("Only workout/hike/food save is enabled in v1.")
        return
    st.success("Saved successfully!")


def render_daily_log_timeline(day: date):
    workouts = safe_dt(fetch_workouts(), "date")
    hikes = safe_dt(fetch_hikes(), "date")
    foods = safe_dt(fetch_foods(), "date")

    events = []
    if not workouts.empty:
        for _, row in workouts[workouts["date"].dt.date == day].iterrows():
            events.append((row["date"], f"🏋️ Workout · {row.get('workout_name') or 'Workout'}"))
    if not hikes.empty:
        for _, row in hikes[hikes["date"].dt.date == day].iterrows():
            events.append((row["date"], f"🥾 Hike · {row.get('trail_name') or 'Hike'}"))
    if not foods.empty:
        for _, row in foods[foods["date"].dt.date == day].iterrows():
            events.append((row["date"], f"🍱 Food · {row.get('meal_type') or 'Meal'}"))

    events.sort(key=lambda x: x[0])
    if not events:
        st.info(f"No log entries for {day.isoformat()}.")
        return

    for _, label in events:
        st.markdown(f"- {label}")


if nav == "Dashboard":
    workouts = safe_dt(fetch_workouts(), "date")
    hikes = safe_dt(fetch_hikes(), "date")
    foods = safe_dt(fetch_foods(), "date")
    trophies = fetch_trophies()
    streaks = compute_streaks()

    ws, we = week_bounds()
    workouts_week = int((workouts["date"].dt.date.between(ws, we)).sum()) if not workouts.empty else 0
    hikes_week = int((hikes["date"].dt.date.between(ws, we)).sum()) if not hikes.empty else 0
    meals_today = int((foods["date"].dt.date == date.today()).sum()) if not foods.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Workouts This Week", workouts_week)
    with c2:
        metric_card("Hikes This Week", hikes_week)
    with c3:
        metric_card("Meals Logged Today", meals_today)
    with c4:
        metric_card("Current Streak", streaks["current"], "days")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        metric_card("Total Miles Hiked", round(float(hikes["distance_miles"].fillna(0).sum()) if not hikes.empty else 0, 1))
    with c6:
        metric_card("Total Workouts", len(workouts))
    with c7:
        avg_cal = round(float(foods["total_calories"].fillna(0).mean()), 0) if not foods.empty else 0
        metric_card("Average Daily Calories", int(avg_cal))
    with c8:
        metric_card("Total Trophies", int((trophies["unlocked"] == 1).sum()))

    st.subheader("Activity Trends")
    a1, a2 = st.columns(2)
    if not workouts.empty:
        wk = workouts.groupby(workouts["date"].dt.to_period("W")).size().reset_index(name="count")
        wk["week"] = wk["date"].astype(str)
    else:
        wk = pd.DataFrame()
    if not hikes.empty:
        hk = hikes.groupby(hikes["date"].dt.to_period("W")).size().reset_index(name="count")
        hk["week"] = hk["date"].astype(str)
    else:
        hk = pd.DataFrame()
    with a1:
        plot_bar(wk, "week", "count", "Workouts by Week")
    with a2:
        plot_bar(hk, "week", "count", "Hikes by Week")

    b1, b2 = st.columns(2)
    with b1:
        if not foods.empty:
            cals = foods.groupby(foods["date"].dt.date)["total_calories"].sum().reset_index()
            cals.columns = ["date", "calories"]
        else:
            cals = pd.DataFrame()
        plot_line(cals, "date", "calories", "Calories by Day")
    with b2:
        if not foods.empty:
            protein = foods.groupby(foods["date"].dt.date)["total_protein"].sum().reset_index()
            protein.columns = ["date", "protein"]
        else:
            protein = pd.DataFrame()
        plot_line(protein, "date", "protein", "Protein by Day")

    c1, c2 = st.columns(2)
    with c1:
        m = workouts.groupby("muscle_group").size().reset_index(name="count") if not workouts.empty else pd.DataFrame()
        plot_pie(m, "muscle_group", "count", "Workout Type Breakdown")
    with c2:
        elev = hikes.groupby(hikes["date"].dt.date)["elevation_gain_ft"].sum().reset_index() if not hikes.empty else pd.DataFrame()
        if not elev.empty:
            elev.columns = ["date", "elevation_gain_ft"]
        plot_line(elev, "date", "elevation_gain_ft", "Total Elevation Over Time")

    st.subheader("Streak Trend")
    if not foods.empty or not hikes.empty or not workouts.empty:
        all_dates = pd.concat(
            [
                workouts[["date"]] if not workouts.empty else pd.DataFrame(columns=["date"]),
                hikes[["date"]] if not hikes.empty else pd.DataFrame(columns=["date"]),
                foods[["date"]] if not foods.empty else pd.DataFrame(columns=["date"]),
            ]
        ).dropna()
        all_dates["day"] = all_dates["date"].dt.date
        logged = sorted(all_dates["day"].unique())
        run, rows = 0, []
        prev = None
        for d in logged:
            run = run + 1 if prev and d == prev + pd.Timedelta(days=1) else 1
            rows.append({"date": d, "streak": run})
            prev = d
        st.line_chart(pd.DataFrame(rows).set_index("date"))

elif nav == "Log Entry":
    st.subheader("📝 Log Entry")
    st.caption("Write one log entry, then submit to auto-parse and save to workout, hike, or food history.")

    text = st.text_area(
        "Entry Text",
        value=st.session_state.get("log_text", ""),
        height=220,
        placeholder="Example: Hiked 4 miles at Mission Peak, then ate a turkey sandwich and did 30 min leg workout.",
    )

    if st.button("Submit", type="primary", use_container_width=True):
        if text.strip():
            st.session_state.log_text = text
            parsed = parse_entry(text)
            st.session_state.last_submit = parsed
            etype = parsed.get("type", "note")
            data = parsed.get("data", {})
            if etype in {"workout", "hike", "food"}:
                save_payload(etype, data)
                st.session_state.log_text = ""
                st.success(f"Submitted and saved as {etype}.")
                st.rerun()
            else:
                st.warning("Entry was parsed as a note. Add clearer workout/hike/food details and submit again.")
        else:
            st.warning("Please type an entry first.")

    st.markdown("---")
    st.subheader("📅 Daily Calendar + Log History")
    selected_day = st.date_input("Select a date to view what happened", value=date.today(), key="log_calendar")
    render_daily_log_timeline(selected_day)

elif nav == "Workout History":
    st.subheader("🏋️ Workout History")
    df = safe_dt(fetch_workouts(), "date")
    c1, c2 = st.columns(2)
    q = c1.text_input("Search workout name/notes")
    selected_day = c2.date_input("Calendar Date", value=date.today(), key="workout_calendar")
    if q:
        df = df[df["workout_name"].fillna("").str.contains(q, case=False) | df["notes"].fillna("").str.contains(q, case=False)]
    st.markdown("#### Selected Day")
    day_df = df[df["date"].dt.date == selected_day]
    if day_df.empty:
        st.info("No workouts for the selected day.")
    else:
        for _, row in day_df.iterrows():
            st.markdown(f"- {row['date'].date()} · **{row['workout_name']}** ({row['muscle_group']})")
    st.markdown("#### Log History")
    st.write(f"Total sessions: **{len(df)}**")
    for _, row in df.iterrows():
        with st.expander(f"{row['date'].date()} · {row['workout_name']} ({row['muscle_group']})"):
            st.write(f"Duration: {row.get('duration_minutes') or 0} min | Cardio: {row.get('cardio_minutes') or 0} min")
            ex = fetch_exercises(int(row["id"]))
            st.dataframe(ex[["exercise_name", "sets", "reps", "weight"]], use_container_width=True)
            if st.button("Delete Workout", key=f"del_w_{row['id']}"):
                delete_entry("workouts", int(row["id"]))
                st.rerun()

elif nav == "Hike History":
    st.subheader("🥾 Hike History")
    df = safe_dt(fetch_hikes(), "date")
    c1, c2 = st.columns(2)
    q = c1.text_input("Search trail/notes")
    selected_day = c2.date_input("Calendar Date", value=date.today(), key="hike_calendar")
    if q:
        df = df[df["trail_name"].fillna("").str.contains(q, case=False) | df["notes"].fillna("").str.contains(q, case=False)]
    st.markdown("#### Selected Day")
    day_df = df[df["date"].dt.date == selected_day]
    if day_df.empty:
        st.info("No hikes for the selected day.")
    else:
        for _, row in day_df.iterrows():
            st.markdown(f"- {row['date'].date()} · **{row['trail_name']}** ({row['distance_miles']} mi)")
    st.markdown("#### Log History")
    st.write(f"Total hikes: **{len(df)}** · Total miles: **{round(df['distance_miles'].fillna(0).sum(),1) if not df.empty else 0}**")
    for _, row in df.iterrows():
        with st.expander(f"{row['date'].date()} · {row['trail_name']} ({row['distance_miles']} mi)"):
            st.write(f"Duration: {row.get('duration_minutes') or 0} min | Elevation: {row.get('elevation_gain_ft') or 0} ft")
            if st.button("Delete Hike", key=f"del_h_{row['id']}"):
                delete_entry("hikes", int(row["id"]))
                st.rerun()

elif nav == "Food History":
    st.subheader("🍱 Food History")
    df = safe_dt(fetch_foods(), "date")
    c1, c2 = st.columns(2)
    q = c1.text_input("Search meal/notes")
    selected_day = c2.date_input("Calendar Date", value=date.today(), key="food_calendar")
    if q:
        df = df[df["meal_type"].fillna("").str.contains(q, case=False) | df["notes"].fillna("").str.contains(q, case=False)]
    st.markdown("#### Selected Day")
    day_df = df[df["date"].dt.date == selected_day]
    if day_df.empty:
        st.info("No food logs for the selected day.")
    else:
        for _, row in day_df.iterrows():
            st.markdown(f"- {row['date'].date()} · **{row['meal_type']}** ({row.get('total_calories') or 0} kcal)")
    st.markdown("#### Log History")
    st.write(f"Meals: **{len(df)}** · Avg protein: **{round(df['total_protein'].fillna(0).mean(),1) if not df.empty else 0} g**")
    for _, row in df.iterrows():
        with st.expander(f"{row['date'].date()} · {row['meal_type']} ({row.get('total_calories') or 0} kcal)"):
            items = fetch_food_items(int(row["id"]))
            st.dataframe(items[["item_name", "estimated_calories", "protein_g", "carbs_g", "fat_g"]], use_container_width=True)
            if st.button("Delete Meal", key=f"del_f_{row['id']}"):
                delete_entry("foods", int(row["id"]))
                st.rerun()

elif nav == "Progress & Stats":
    st.subheader("📈 Progress & Stats")
    workouts = safe_dt(fetch_workouts(), "date")
    hikes = safe_dt(fetch_hikes(), "date")
    foods = safe_dt(fetch_foods(), "date")
    streaks = compute_streaks()

    total_sets = 0
    est_weight = 0.0
    for _, row in workouts.iterrows():
        ex = fetch_exercises(int(row["id"]))
        if not ex.empty:
            total_sets += int(ex["sets"].fillna(0).sum())
            est_weight += float((ex["sets"].fillna(0) * ex["reps"].fillna(0) * ex["weight"].fillna(0)).sum())

    weekly_workouts = workouts[workouts["date"].dt.date >= (date.today() - pd.Timedelta(days=7))].shape[0] if not workouts.empty else 0
    monthly_workouts = workouts[workouts["date"].dt.date >= (date.today() - pd.Timedelta(days=30))].shape[0] if not workouts.empty else 0
    most_group = workouts["muscle_group"].mode().iloc[0] if not workouts.empty and workouts["muscle_group"].notna().any() else "N/A"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Weekly Workouts", weekly_workouts)
    c2.metric("Monthly Workouts", monthly_workouts)
    c3.metric("Workout Streak", streaks["current"])
    c4.metric("Total Sets", total_sets)

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Estimated Weight Lifted", f"{int(est_weight):,} lb")
    d2.metric("Most Trained Group", most_group)
    d3.metric("Total Hikes", len(hikes))
    d4.metric("Total Miles", round(float(hikes['distance_miles'].fillna(0).sum()) if not hikes.empty else 0, 1))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Avg Hike Distance", round(float(hikes['distance_miles'].fillna(0).mean()) if not hikes.empty else 0, 1))
    e2.metric("Total Elevation", int(hikes["elevation_gain_ft"].fillna(0).sum()) if not hikes.empty else 0)
    e3.metric("Avg Calories", int(foods["total_calories"].fillna(0).mean()) if not foods.empty else 0)
    e4.metric("Avg Protein", round(float(foods["total_protein"].fillna(0).mean()) if not foods.empty else 0, 1))

    consistency = round((streaks["days_this_month"] / max(date.today().day, 1)) * 100)
    st.metric("Logging Consistency Score", f"{consistency}%")

    st.markdown("---")
    cals = foods.groupby(foods["date"].dt.date)["total_calories"].sum().reset_index() if not foods.empty else pd.DataFrame()
    protein = foods.groupby(foods["date"].dt.date)["total_protein"].sum().reset_index() if not foods.empty else pd.DataFrame()
    hikes_week = hikes.groupby(hikes["date"].dt.to_period("W")).size().reset_index(name="count") if not hikes.empty else pd.DataFrame()
    workouts_week = workouts.groupby(workouts["date"].dt.to_period("W")).size().reset_index(name="count") if not workouts.empty else pd.DataFrame()

    if not cals.empty:
        cals.columns = ["date", "calories"]
    if not protein.empty:
        protein.columns = ["date", "protein"]
    if not hikes_week.empty:
        hikes_week["week"] = hikes_week["date"].astype(str)
    if not workouts_week.empty:
        workouts_week["week"] = workouts_week["date"].astype(str)

    c1, c2 = st.columns(2)
    with c1:
        plot_line(cals, "date", "calories", "Calories over Time")
        plot_bar(workouts_week, "week", "count", "Workouts per Week")
    with c2:
        plot_line(protein, "date", "protein", "Protein over Time")
        plot_bar(hikes_week, "week", "count", "Hikes per Week")

elif nav == "Trophies / Awards":
    st.subheader("🏆 Trophies & Awards")
    refresh_trophies()
    trophies = fetch_trophies()

    unlocked = trophies[trophies["unlocked"] == 1]
    locked = trophies[trophies["unlocked"] == 0]

    st.metric("Unlocked Trophies", len(unlocked))

    st.markdown("### Unlocked")
    if unlocked.empty:
        st.info("Start logging to earn your first trophy.")
    for _, t in unlocked.iterrows():
        st.markdown(
            f"<div class='trophy'><b>{t['emoji']} {t['name']}</b><br><span class='pf-sub'>{t['description']}</span><br>Earned: <b>{t['unlocked_date']}</b></div>",
            unsafe_allow_html=True,
        )

    st.markdown("### In Progress")
    for _, t in locked.iterrows():
        target = t["target"] if t["target"] else 1
        p = min(float(t["progress"] or 0) / float(target), 1.0)
        st.markdown(
            f"<div class='trophy locked'><b>{t['emoji']} {t['name']}</b><br><span class='pf-sub'>{t['description']}</span></div>",
            unsafe_allow_html=True,
        )
        st.progress(p, text=f"{round(float(t['progress'] or 0),1)} / {target}")

    st.markdown("---")
    st.subheader("Profile Goals")
    profile = fetch_profile()
    c1, c2, c3, c4 = st.columns(4)
    calorie_goal = c1.number_input("Calorie Goal", value=float(profile.get("calorie_goal", 2400)), step=50.0)
    protein_goal = c2.number_input("Protein Goal", value=float(profile.get("protein_goal", 160)), step=5.0)
    weekly_workout_goal = c3.number_input("Weekly Workout Goal", value=int(profile.get("weekly_workout_goal", 4)), step=1)
    weekly_hike_goal = c4.number_input("Weekly Hike Goal", value=int(profile.get("weekly_hike_goal", 2)), step=1)

    if st.button("Save Goals"):
        update_profile(
            {
                "calorie_goal": calorie_goal,
                "protein_goal": protein_goal,
                "weekly_workout_goal": weekly_workout_goal,
                "weekly_hike_goal": weekly_hike_goal,
            }
        )
        refresh_trophies()
        st.success("Goals saved")
