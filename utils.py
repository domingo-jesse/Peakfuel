from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {background: #f6f8fb; color: #0f172a;}
        [data-testid="stSidebar"] {background: #ffffff; border-right: 1px solid #e2e8f0;}
        .block-container {padding-top: 1.25rem; padding-bottom: 2rem;}
        .pf-card {background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);}
        .pf-title {font-weight: 700; font-size: 1.05rem; margin-bottom: .25rem; color: #1e293b;}
        .pf-sub {color: #475569; font-size: .85rem;}
        .trophy {border-radius: 14px; border: 1px solid #e2e8f0; padding: .75rem; margin-bottom: .65rem; background: #ffffff;}
        .trophy.locked {opacity: .6;}
        h1,h2,h3 {letter-spacing: .2px; color: #0f172a;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def week_bounds():
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def metric_card(title: str, value, subtitle: str = ""):
    st.markdown(
        f"""
        <div class='pf-card'>
            <div class='pf-title'>{title}</div>
            <div style='font-size:1.8rem;font-weight:700'>{value}</div>
            <div class='pf-sub'>{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def safe_dt(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns and not df.empty:
        df = df.copy()
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def weekly_counts(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    if df.empty or date_col not in df.columns:
        return pd.DataFrame()
    weekly = (
        df.assign(week_start=df[date_col].dt.to_period("W-SUN").dt.start_time.dt.date)
        .groupby("week_start")
        .size()
        .reset_index(name="count")
        .sort_values("week_start")
    )
    weekly["week"] = pd.to_datetime(weekly["week_start"]).dt.strftime("%b %d")
    return weekly


def _render_plotly(fig):
    fig.update_layout(
        height=320,
        margin=dict(l=12, r=12, t=46, b=12),
        dragmode=False,
        xaxis_fixedrange=True,
        yaxis_fixedrange=True,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#0f172a"),
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "staticPlot": True,
            "displayModeBar": False,
        },
    )


def plot_line(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.line(df, x=x, y=y, markers=True, title=title, template="plotly_white")
    _render_plotly(fig)


def plot_bar(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.bar(df, x=x, y=y, title=title, template="plotly_white")
    _render_plotly(fig)


def plot_pie(df: pd.DataFrame, names: str, values: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.pie(df, names=names, values=values, title=title, hole=0.45, template="plotly_white")
    fig.update_layout(height=330)
    _render_plotly(fig)
