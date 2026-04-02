from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%); color: #0f172a;}
        [data-testid="stSidebar"] {background: #f1f5f9; border-right: 1px solid #dbe3ee;}
        .pf-card {background: #ffffff; border: 1px solid #dbe3ee; border-radius: 16px; padding: 1rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);}
        .pf-title {font-weight: 700; font-size: 1.05rem; margin-bottom: .25rem; color: #1e293b;}
        .pf-sub {color: #64748b; font-size: .85rem;}
        .trophy {border-radius: 14px; border: 1px solid #dbe3ee; padding: .75rem; margin-bottom: .65rem; background: #ffffff;}
        .trophy.locked {opacity: .6;}
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
    fig = px.line(df, x=x, y=y, markers=True, title=title, template="plotly_white")
    fig.update_layout(height=320, margin=dict(l=12, r=12, t=46, b=12))
    st.plotly_chart(fig, use_container_width=True)


def plot_bar(df: pd.DataFrame, x: str, y: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.bar(df, x=x, y=y, title=title, template="plotly_white")
    fig.update_layout(height=320, margin=dict(l=12, r=12, t=46, b=12))
    st.plotly_chart(fig, use_container_width=True)


def plot_pie(df: pd.DataFrame, names: str, values: str, title: str):
    if df.empty:
        st.info("No data yet.")
        return
    fig = px.pie(df, names=names, values=values, title=title, hole=0.45, template="plotly_white")
    fig.update_layout(height=330, margin=dict(l=12, r=12, t=46, b=12))
    st.plotly_chart(fig, use_container_width=True)
