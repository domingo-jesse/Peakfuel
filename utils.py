from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {background: linear-gradient(180deg, #0b0f14 0%, #111827 100%); color: #e5e7eb;}
        [data-testid="stSidebar"] {background: #0f172a;}
        .pf-card {background: rgba(17,24,39,.82); border: 1px solid #374151; border-radius: 16px; padding: 1rem; margin-bottom: 1rem;}
        .pf-title {font-weight: 700; font-size: 1.05rem; margin-bottom: .25rem; color: #f3f4f6;}
        .pf-sub {color: #9ca3af; font-size: .85rem;}
        .trophy {border-radius: 14px; border: 1px solid #374151; padding: .75rem; margin-bottom: .65rem; background: #111827;}
        .trophy.locked {opacity: .5;}
        h1,h2,h3 {letter-spacing: .2px;}
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
        df[col] = pd.to_datetime(df[col])
    return df


def plot_line(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.line(df, x=x, y=y, markers=True, title=title, template="plotly_dark")
    fig.update_layout(height=320, margin=dict(l=12, r=12, t=46, b=12))
    st.plotly_chart(fig, use_container_width=True)


def plot_bar(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.bar(df, x=x, y=y, title=title, template="plotly_dark")
    fig.update_layout(height=320, margin=dict(l=12, r=12, t=46, b=12))
    st.plotly_chart(fig, use_container_width=True)


def plot_pie(df: pd.DataFrame, names: str, values: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.pie(df, names=names, values=values, title=title, hole=0.45, template="plotly_dark")
    fig.update_layout(height=330, margin=dict(l=12, r=12, t=46, b=12))
    st.plotly_chart(fig, use_container_width=True)
