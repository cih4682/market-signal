"""Coupang & YouTube Review Studio — Streamlit 기반 탭형 추출기."""
from __future__ import annotations

import html as _html
import io
import re
from datetime import datetime
from textwrap import dedent

import pandas as pd
import streamlit as st

from crawler import crawl_reviews, parse_product_url
from naver_crawler import crawl_naver_reviews, parse_naver_url
from news_crawler import (
    crawl_news,
    extract_article_content,
    summarize_text,
    CATEGORIES as NEWS_CATEGORIES,
    PERIOD_QUERY as NEWS_PERIODS,
)
from youtube_crawler import crawl_youtube_comments, parse_video_id
from youtube_search import search_trends, humanize


def html(markup: str) -> None:
    """들여쓰기와 빈 줄을 제거한 HTML을 안전하게 렌더링."""
    cleaned = "\n".join(
        line for line in dedent(markup).splitlines() if line.strip()
    )
    st.markdown(cleaned, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Market Signal",
    page_icon="◎",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ─────────────────────────────────────────────────────────────────
# 라인 스타일 SVG 아이콘 (Lucide 계열)
# ─────────────────────────────────────────────────────────────────
def icon(name: str, size: int = 18) -> str:
    paths = {
        "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
        "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
        "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
        "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
        "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
        "table": '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/><line x1="15" y1="3" x2="15" y2="21"/>',
        "sparkle": '<path d="M12 3l1.9 5.6L19 10l-5.1 1.4L12 17l-1.9-5.6L5 10l5.1-1.4L12 3z"/>',
        "check": '<polyline points="20 6 9 17 4 12"/>',
        "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
        "alert": '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
        "package": '<line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
        "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
        "key": '<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>',
        "play": '<polygon points="5 3 19 12 5 21 5 3"/>',
        "heart": '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
        "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
        "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        "sort": '<path d="M7 3v18"/><path d="M3 7l4-4 4 4"/><path d="M17 21V3"/><path d="M21 17l-4 4-4-4"/>',
        "radar": '<circle cx="12" cy="12" r="2.5"/><circle cx="12" cy="12" r="6.5"/><circle cx="12" cy="12" r="10.5"/>',
    }
    body = paths.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:-3px;margin-right:8px;flex-shrink:0;">{body}</svg>'
    )


# ─────────────────────────────────────────────────────────────────
# 글로벌 스타일
# ─────────────────────────────────────────────────────────────────
html("""
<link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
<style>
:root { --bg: #f6f6f4; --surface: #ffffff; --border: #e3e3e0; --border-strong: #cccccc; --text: #0a0a0a; --text-2: #1f1f1f; --label: #2a2a2a; --muted: #595959; --accent-soft: #ededea; }
html, body, [class*="css"], .stApp, .stMarkdown, .stTextInput input, .stButton button, .stSlider, .stRadio, .stSelectbox, .stDataFrame, .stCheckbox, [data-testid="stWidgetLabel"], [data-testid="stMarkdownContainer"], [data-baseweb="select"] *, .stTabs button { font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', sans-serif !important; letter-spacing: -0.005em; }
html, body { font-size: 17px; }
.stApp { background: var(--bg); color: var(--text-2); }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 4rem; padding-bottom: 5rem; max-width: 1120px; }
.brand { display: flex; align-items: center; gap: 16px; padding: 0 0 12px 0; }
.brand-mark { width: 44px; height: 44px; border: 2.25px solid var(--text); display: flex; align-items: center; justify-content: center; border-radius: 12px; flex-shrink: 0; }
.brand-mark svg { width: 22px; height: 22px; stroke-width: 2 !important; }
.brand-text { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.brand-title { font-size: 15px; font-weight: 800; color: var(--text); letter-spacing: 0.18em; }
.brand-sub { font-size: 14px; color: var(--muted); margin-top: 2px; font-weight: 500; letter-spacing: 0.01em; }
.brand-status { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 700; color: var(--muted); letter-spacing: 0.14em; text-transform: uppercase; padding-left: 12px; }
.brand-dot { width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18); animation: brand-pulse 2.4s ease-in-out infinite; flex-shrink: 0; }
@keyframes brand-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.55; transform: scale(0.92); } }
.hero { margin: 22px 0 36px 0; }
.hero h1 { font-size: 48px; font-weight: 800; color: var(--text); line-height: 1.2; letter-spacing: -0.028em; margin: 0 0 16px 0; }
.hero p { font-size: 18px; color: var(--muted); margin: 0; font-weight: 500; line-height: 1.55; }
.card-title { font-size: 16px; font-weight: 700; color: var(--label); margin-bottom: 12px; display: flex; align-items: center; gap: 2px; }
.card-title svg { color: var(--text); width: 19px; height: 19px; }
.stTextInput > div > div > input, .stTextInput input[type="password"] { border: 1.5px solid var(--border-strong) !important; background: var(--surface) !important; border-radius: 12px !important; padding: 17px 18px !important; font-size: 17px !important; font-weight: 500 !important; color: var(--text) !important; height: auto !important; transition: border-color .15s ease; }
.stTextInput > div > div > input:focus { border-color: var(--text) !important; box-shadow: 0 0 0 3px rgba(0,0,0,0.04) !important; }
.stTextInput > div > div > input::placeholder { color: #999 !important; font-weight: 400; }
[data-testid="stWidgetLabel"] p { font-size: 15px !important; font-weight: 600 !important; color: var(--label) !important; letter-spacing: 0; }
.stSelectbox > div { background: transparent !important; }
[data-baseweb="select"] > div { border: 1.5px solid var(--border-strong) !important; border-radius: 12px !important; height: 62px !important; min-height: 62px !important; max-height: 62px !important; background: var(--surface) !important; display: flex !important; align-items: center !important; padding: 0 6px !important; box-sizing: border-box !important; }
[data-baseweb="select"] > div > div { font-size: 17px !important; font-weight: 600 !important; color: var(--text) !important; display: flex !important; align-items: center !important; padding: 0 10px !important; height: auto !important; min-height: 0 !important; }
[data-baseweb="select"] [data-baseweb="select-arrow"] { display: flex !important; align-items: center !important; }
[data-baseweb="popover"] li { font-size: 16px !important; font-weight: 500 !important; padding: 13px 16px !important; }
.stSlider, .stSlider * { font-family: 'Pretendard Variable', Pretendard, -apple-system, system-ui, sans-serif !important; }
.stSlider [data-baseweb="slider"] { padding: 30px 12px 14px 12px !important; overflow: visible !important; }
.stSlider [data-baseweb="slider"] > div { background: transparent !important; height: 8px !important; overflow: visible !important; }
.stSlider [data-baseweb="slider"] > div > div { background: #e5e5e2 !important; height: 8px !important; border-radius: 999px !important; box-shadow: inset 0 1.5px 3px rgba(0,0,0,0.08), inset 0 -1px 0 rgba(255,255,255,0.6) !important; }
.stSlider [data-baseweb="slider"] > div > div > div:first-of-type { background: linear-gradient(90deg, #000000 0%, #1a1a1a 100%) !important; height: 8px !important; border-radius: 999px !important; box-shadow: 0 1px 3px rgba(0,0,0,0.25) !important; }
.stSlider [data-baseweb="slider"] [role="slider"] { background: #ffffff !important; border: 2.5px solid #0a0a0a !important; width: 28px !important; height: 28px !important; border-radius: 50% !important; box-shadow: 0 2px 4px rgba(0,0,0,0.08), 0 6px 18px rgba(0,0,0,0.18), inset 0 -2px 5px rgba(0,0,0,0.06) !important; transition: transform 0.18s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.18s ease !important; cursor: grab; position: relative !important; }
.stSlider [data-baseweb="slider"] [role="slider"]::before { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 8px; height: 8px; border-radius: 50%; background: #0a0a0a; }
.stSlider [data-baseweb="slider"] [role="slider"]:hover { transform: scale(1.12); box-shadow: 0 3px 6px rgba(0,0,0,0.12), 0 10px 28px rgba(0,0,0,0.28), inset 0 -2px 5px rgba(0,0,0,0.08) !important; }
.stSlider [data-baseweb="slider"] [role="slider"]:active { transform: scale(1.06); cursor: grabbing; }
.stSlider [data-baseweb="slider"] [role="slider"]:focus, .stSlider [data-baseweb="slider"] [role="slider"]:focus-visible { outline: none !important; }
.stSlider div[data-testid="stTickBarMin"], .stSlider div[data-testid="stTickBarMax"] { font-family: 'Pretendard Variable', Pretendard, sans-serif !important; font-size: 13px !important; font-weight: 700 !important; color: var(--text-2) !important; opacity: 0.65 !important; letter-spacing: -0.01em !important; padding-top: 12px !important; font-variant-numeric: tabular-nums !important; line-height: 1 !important; }
.stSlider [data-testid="stThumbValue"] { font-family: 'Pretendard Variable', Pretendard, sans-serif !important; font-size: 13.5px !important; font-weight: 800 !important; color: #ffffff !important; background: linear-gradient(135deg, #0a0a0a 0%, #2c2c2c 100%) !important; padding: 6px 12px !important; border-radius: 8px !important; letter-spacing: -0.01em !important; font-variant-numeric: tabular-nums !important; box-shadow: 0 2px 4px rgba(0,0,0,0.1), 0 6px 16px rgba(0,0,0,0.22) !important; line-height: 1 !important; min-width: 0 !important; position: relative !important; top: -6px !important; white-space: nowrap !important; }
.stSlider [data-testid="stThumbValue"]::after { content: ''; position: absolute; left: 50%; bottom: -4px; width: 8px; height: 8px; background: #2c2c2c; transform: translateX(-50%) rotate(45deg); border-radius: 1.5px; z-index: -1; }
.stNumberInput { width: 100%; position: relative !important; }
.stNumberInput > div { background: transparent !important; position: relative !important; width: 100% !important; }
.stNumberInput [data-baseweb="input"] { border: 1.5px solid var(--border-strong) !important; border-radius: 12px !important; background: var(--surface) !important; height: 62px !important; min-height: 62px !important; max-height: 62px !important; display: flex !important; align-items: center !important; padding: 0 !important; transition: border-color .15s ease, box-shadow .15s ease; overflow: visible !important; box-shadow: none !important; width: 100% !important; box-sizing: border-box !important; }
.stNumberInput [data-baseweb="input"]:focus-within { border-color: var(--text) !important; box-shadow: 0 0 0 3px rgba(0,0,0,0.04) !important; }
.stNumberInput [data-baseweb="input-container"] { flex: 1 !important; background: transparent !important; border: none !important; padding: 0 !important; display: flex !important; align-items: center !important; height: 100% !important; }
.stNumberInput input { font-family: 'Pretendard Variable', Pretendard, sans-serif !important; font-size: 17px !important; font-weight: 700 !important; color: var(--text) !important; background: transparent !important; border: none !important; padding: 0 64px 0 18px !important; width: 100% !important; font-variant-numeric: tabular-nums !important; letter-spacing: -0.01em !important; height: 100% !important; outline: none !important; box-shadow: none !important; }
.stNumberInput input::-webkit-outer-spin-button, .stNumberInput input::-webkit-inner-spin-button { -webkit-appearance: none !important; margin: 0 !important; }
.stNumberInput [data-testid="stNumberInputStepUp"], .stNumberInput [data-testid="stNumberInputStepDown"] { position: absolute !important; right: 8px !important; width: 34px !important; min-width: 34px !important; height: 25px !important; background: transparent !important; border: none !important; border-radius: 6px !important; display: flex !important; align-items: center !important; justify-content: center !important; color: var(--muted) !important; cursor: pointer !important; margin: 0 !important; padding: 0 !important; z-index: 5 !important; transition: background .12s ease, color .12s ease !important; }
.stNumberInput [data-testid="stNumberInputStepUp"] { top: 5px !important; }
.stNumberInput [data-testid="stNumberInputStepDown"] { bottom: 5px !important; }
.stNumberInput button:hover { background: var(--accent-soft) !important; color: var(--text) !important; }
.stNumberInput button:active { background: var(--text) !important; color: #fff !important; }
.stNumberInput button svg { width: 12px !important; height: 12px !important; stroke-width: 2.25 !important; }
.stCheckbox label { font-size: 16px !important; font-weight: 600 !important; color: var(--text-2) !important; }
.stCheckbox label p { font-size: 16px !important; font-weight: 600 !important; color: var(--text-2) !important; }
.stButton > button { background: var(--text) !important; color: #fff !important; border: none !important; border-radius: 12px !important; padding: 19px 28px !important; font-size: 18px !important; font-weight: 700 !important; letter-spacing: -0.005em; width: 100%; transition: transform .15s ease, box-shadow .15s ease; box-shadow: 0 1px 2px rgba(0,0,0,0.06); }
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(0,0,0,0.12); }
.stButton > button:active { transform: translateY(0); }
.stDownloadButton > button { background: var(--surface) !important; color: var(--text) !important; border: 1.5px solid var(--text) !important; border-radius: 12px !important; padding: 17px 24px !important; font-size: 17px !important; font-weight: 700 !important; width: 100%; }
.stDownloadButton > button:hover { background: var(--text) !important; color: #fff !important; }
.metric-grid { display: grid; gap: 14px; margin-bottom: 26px; }
.metric { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 24px 26px; }
.metric-label { font-size: 15px; color: var(--muted); font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; gap: 4px; }
.metric-label svg { width: 15px; height: 15px; }
.metric-value { font-size: 34px; font-weight: 800; color: var(--text); letter-spacing: -0.025em; line-height: 1.1; }
.metric-value .unit { font-size: 15px; color: var(--muted); font-weight: 600; margin-left: 6px; }
.notice { display: flex; gap: 12px; align-items: center; font-size: 15px; font-weight: 500; color: var(--text-2); background: var(--accent-soft); border-radius: 12px; padding: 17px 20px; margin: 16px 0 4px 0; }
.notice svg { flex-shrink: 0; color: var(--text); width: 18px; height: 18px; }
.notice.error { background: #fff4f4; color: #b00020; }
.notice.error svg { color: #b00020; }
.stProgress > div > div { background: var(--border) !important; height: 6px !important; border-radius: 4px !important; }
.stProgress > div > div > div { background: var(--text) !important; height: 6px !important; border-radius: 4px !important; }
.stProgress p { font-size: 15px !important; font-weight: 600 !important; color: var(--text) !important; }
.review-table-wrap { border: 1px solid var(--border); border-radius: 14px; overflow: auto; max-height: 640px; background: var(--surface); box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
.review-table { width: 100%; border-collapse: collapse; font-size: 16px; table-layout: fixed; }
.review-table thead { position: sticky; top: 0; background: #ffffff; z-index: 2; }
.review-table thead::after { content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 1.5px; background: var(--text); }
.review-table th { text-align: left; font-weight: 700; color: var(--text); padding: 16px 16px; font-size: 14.5px; letter-spacing: -0.005em; white-space: nowrap; }
.review-table td { padding-left: 16px !important; padding-right: 16px !important; }
.review-table td { padding: 18px 20px; border-bottom: 1px solid var(--border); vertical-align: top; color: var(--text-2); line-height: 1.6; }
.review-table tbody tr:hover { background: #fafaf9; }
.review-table tr:last-child td { border-bottom: none; }
.review-table .c-no { text-align: right; color: var(--muted); font-weight: 600; font-variant-numeric: tabular-nums; font-size: 15px; }
.review-table .c-name { white-space: nowrap; font-weight: 600; color: var(--text); font-size: 15.5px; }
.review-table .c-date { white-space: nowrap; color: var(--muted); font-weight: 500; font-variant-numeric: tabular-nums; font-size: 15px; }
.review-table .c-option { font-size: 14.5px; color: var(--muted); font-weight: 500; word-break: keep-all; }
.review-table .c-review { font-size: 16px; line-height: 1.7; color: var(--text-2); word-break: break-word; white-space: pre-wrap; font-weight: 500; }
.review-table .c-num { text-align: right; color: var(--muted); font-weight: 600; font-variant-numeric: tabular-nums; font-size: 15px; }
.review-table .c-tag { display: inline-block; padding: 4px 12px; border-radius: 999px; background: var(--accent-soft); color: var(--text-2); font-size: 13px; font-weight: 600; white-space: nowrap; }
.review-table .c-tag.reply { background: #fff; border: 1px solid var(--border-strong); color: var(--muted); }
.video-meta { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 22px; margin-bottom: 18px; display: flex; align-items: center; gap: 14px; }
.video-meta svg { color: var(--text); flex-shrink: 0; }
.video-meta-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.video-meta-title { font-size: 16px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.video-meta-channel { font-size: 14px; color: var(--muted); font-weight: 500; }
.review-table .c-thumb { padding: 12px 14px; }
.review-table .c-thumb img { width: 140px; height: 78px; object-fit: cover; border-radius: 8px; display: block; background: #eee; }
.review-table .c-title-cell { padding-right: 12px; }
.review-table .c-title-link { font-size: 15.5px; font-weight: 700; color: var(--text); text-decoration: none; line-height: 1.45; display: block; word-break: keep-all; }
.review-table .c-title-link:hover { text-decoration: underline; }
.review-table .c-channel { display: flex; flex-direction: column; gap: 3px; }
.review-table .c-channel-name { font-size: 14.5px; font-weight: 600; color: var(--text); word-break: keep-all; }
.review-table .c-channel-subs { font-size: 13px; color: var(--muted); font-weight: 500; }
.score-pill { display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 999px; font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.005em; line-height: 1; }
.score-pill.s-low { background: #f1f1ee; color: var(--muted); }
.score-pill.s-mid { background: #eef4ff; color: #1d4ed8; }
.score-pill.s-high { background: #fff4e0; color: #b45309; }
.score-pill.s-fire { background: #0a0a0a; color: #ffffff; }
.eng-pill { display: inline-flex; padding: 5px 11px; border-radius: 7px; font-size: 13.5px; font-weight: 700; background: var(--accent-soft); color: var(--text-2); font-variant-numeric: tabular-nums; }
.review-table .c-stat { font-variant-numeric: tabular-nums; font-weight: 700; color: var(--text); font-size: 15px; }
.review-table .c-stat-sub { font-size: 12.5px; color: var(--muted); font-weight: 500; }
.review-table .c-meta { font-size: 13px; color: var(--muted); font-weight: 500; }
.quota-bar { display: inline-flex; align-items: center; gap: 6px; background: #ffffff; border: 1px solid var(--border); color: var(--text-2); padding: 9px 15px; border-radius: 999px; font-size: 14px; font-weight: 700; white-space: nowrap; flex-shrink: 0; font-variant-numeric: tabular-nums; }
.kw-chart { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 22px 24px; margin-bottom: 26px; }
.kw-row { display: grid; grid-template-columns: 110px 1fr 56px; align-items: center; gap: 14px; padding: 7px 0; }
.kw-name { font-size: 14.5px; font-weight: 700; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kw-bar-track { background: var(--accent-soft); height: 8px; border-radius: 999px; overflow: hidden; }
.kw-bar-fill { background: linear-gradient(90deg, #0a0a0a 0%, #2c2c2c 100%); height: 100%; border-radius: 999px; transition: width .4s ease; }
.kw-count { font-size: 13.5px; font-weight: 700; color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
.review-table .c-source { font-size: 14px; font-weight: 600; color: var(--text-2); white-space: nowrap; text-align: center; }
[role="dialog"], [data-testid="stDialog"] { border-radius: 22px !important; background: #ffffff !important; border: 1px solid rgba(0,0,0,0.06) !important; box-shadow: 0 24px 64px rgba(0,0,0,0.24), 0 8px 24px rgba(0,0,0,0.10) !important; overflow: hidden !important; max-width: 820px !important; animation: modalFadeIn 0.32s cubic-bezier(0.34, 1.56, 0.64, 1); }
[data-baseweb="modal"] [data-baseweb="modal-backdrop"], [data-baseweb="modal-overlay"] { background: rgba(10, 10, 10, 0.5) !important; backdrop-filter: blur(8px) !important; -webkit-backdrop-filter: blur(8px) !important; }
@keyframes modalFadeIn { from { opacity: 0; transform: scale(0.94) translateY(12px); } to { opacity: 1; transform: scale(1) translateY(0); } }
[role="dialog"] [data-testid="stDialogTitle"], [role="dialog"] h1:first-child { display: none !important; }
[role="dialog"] [data-testid="stDialogContent"], [role="dialog"] > div:first-child { padding: 36px 40px 32px 40px !important; }
[role="dialog"] button[aria-label="Close"], [role="dialog"] [data-testid="stDialogCloseButton"] { width: 36px !important; height: 36px !important; border-radius: 10px !important; background: transparent !important; border: 1px solid var(--border) !important; color: var(--text-2) !important; transition: background .15s ease, border-color .15s ease; top: 22px !important; right: 22px !important; }
[role="dialog"] button[aria-label="Close"]:hover { background: var(--accent-soft) !important; border-color: var(--text) !important; color: var(--text) !important; }
[role="dialog"] .stExpander { border: 1px solid var(--border) !important; border-radius: 12px !important; background: #fafaf9 !important; margin-top: 6px !important; }
[role="dialog"] .stExpander summary { font-weight: 700 !important; color: var(--text) !important; font-size: 14px !important; padding: 14px 18px !important; }
[role="dialog"] .stLinkButton button, [role="dialog"] [data-testid="stLinkButton"] a { background: var(--text) !important; color: #fff !important; border: none !important; border-radius: 12px !important; padding: 16px 24px !important; font-size: 16px !important; font-weight: 700 !important; transition: transform .15s ease, box-shadow .15s ease; }
[role="dialog"] .stLinkButton button:hover, [role="dialog"] [data-testid="stLinkButton"] a:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(0,0,0,0.18); }
.modal-eyebrow { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 700; color: var(--muted); letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 18px; }
.modal-eyebrow-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text); }
.modal-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.modal-chip { display: inline-flex; align-items: center; background: var(--text); color: #ffffff; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 700; letter-spacing: -0.005em; }
.modal-date { color: var(--muted); font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }
.modal-title { font-size: 26px; font-weight: 800; line-height: 1.35; color: var(--text); letter-spacing: -0.028em; word-break: keep-all; margin: 0 0 26px 0; }
.modal-card { position: relative; background: linear-gradient(135deg, #f9f9f7 0%, #efefed 100%); border: 1px solid var(--border); border-radius: 16px; padding: 22px 24px 22px 28px; margin-bottom: 22px; overflow: hidden; }
.modal-card::before { content: ''; position: absolute; left: 0; top: 16px; bottom: 16px; width: 3px; background: var(--text); border-radius: 0 4px 4px 0; }
.modal-card.warn::before { background: #b45309; }
.modal-card-label { display: flex; align-items: center; font-size: 12px; font-weight: 700; color: var(--muted); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 10px; }
.modal-card-text { font-size: 16px; line-height: 1.72; color: var(--text-2); font-weight: 500; word-break: keep-all; }
.modal-body-text { font-size: 15px; line-height: 1.78; color: var(--text-2); font-weight: 400; word-break: keep-all; white-space: pre-wrap; padding: 4px 0; }
.modal-footer-spacer { height: 12px; }
[role="dialog"] [data-testid="stSpinner"] { background: transparent !important; padding: 12px 0 !important; }
.review-table .c-center { text-align: center !important; }
.review-table.news-table th { text-align: center !important; }
.review-table.news-table .c-no { text-align: center !important; }
.review-table.news-table .c-date { text-align: center !important; white-space: nowrap; }
.review-table .c-headline { font-size: 16px; font-weight: 700; color: var(--text); line-height: 1.5; word-break: keep-all; }
.review-table .c-headline a { color: inherit; text-decoration: none; }
.review-table .c-headline a:hover { text-decoration: underline; }
.review-table .c-summary { font-size: 14px; color: var(--text-2); line-height: 1.55; margin-top: 6px; word-break: keep-all; font-weight: 500; }
.quota-bar svg { margin-right: 0 !important; vertical-align: 0 !important; }
.notice.split { justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.notice.split .notice-main { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 240px; }
.notice.split .notice-main svg { margin-right: 0 !important; }
.notice.split .notice-main span { line-height: 1.55; }
.stTabs [data-baseweb="tab-list"] { gap: 0 !important; border-bottom: 1.5px solid var(--border) !important; margin-bottom: 36px !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; border: none !important; padding: 14px 6px !important; margin-right: 32px !important; height: auto !important; font-size: 17px !important; font-weight: 700 !important; color: #999 !important; letter-spacing: 0.02em !important; }
.stTabs [data-baseweb="tab"]:hover { color: var(--text-2) !important; background: transparent !important; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color: var(--text) !important; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--text) !important; height: 2.5px !important; border-radius: 2px !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }
.footer { text-align: center; color: var(--muted); font-size: 14px; font-weight: 500; margin-top: 48px; }
.footer hr { border: none; border-top: 1px solid var(--border); margin-bottom: 18px; }
.footer svg { width: 13px; height: 13px; vertical-align: -2px; }
#MainMenu, footer, header [data-testid="stToolbar"] { visibility: hidden; }
</style>
""")


# ─────────────────────────────────────────────────────────────────
# 헤더
# ─────────────────────────────────────────────────────────────────
html(f"""
<div class="brand">
<div class="brand-mark">{icon("radar", 22)}</div>
<div class="brand-text">
<div class="brand-title">MARKET SIGNAL</div>
<div class="brand-sub">Reviews · Comments · Trends · News</div>
</div>
<div class="brand-status"><span class="brand-dot"></span>Live</div>
</div>
<div class="hero">
<h1>시장의 신호를<br/>한 화면에서 포착하세요.</h1>
<p>리뷰 · 댓글 · 트렌드 · 뉴스를 수집·요약해 엑셀로 내려받습니다.</p>
</div>
""")


# ─────────────────────────────────────────────────────────────────
# 공용 유틸
# ─────────────────────────────────────────────────────────────────
def _esc(v) -> str:
    return _html.escape(str(v) if v is not None else "")


def _show_error(message: str) -> None:
    html(f'<div class="notice error">{icon("alert", 18)}<span>{_esc(message)}</span></div>')


def _show_info(message: str) -> None:
    html(f'<div class="notice">{icon("info", 18)}<span>{_esc(message)}</span></div>')


def _parse_count(value, default: int, min_val: int, max_val: int) -> int:
    """텍스트 입력값을 정수로 안전 변환 + 범위 클램핑."""
    if value is None:
        return default
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return default
    return max(min_val, min(max_val, int(digits)))


# ─────────────────────────────────────────────────────────────────
# 네이버 탭
# ─────────────────────────────────────────────────────────────────
def render_naver() -> None:
    if "nv_df" not in st.session_state:
        st.session_state.nv_df = None
        st.session_state.nv_product_id = None

    html(f'<div class="card-title">{icon("link", 18)}네이버 상품 링크</div>')
    url = st.text_input(
        label="URL",
        label_visibility="collapsed",
        placeholder="https://smartstore.naver.com/{스토어}/products/...  또는  https://brand.naver.com/...",
        key="nv_url",
    )

    html('<div style="height:24px;"></div>')

    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        html(f'<div class="card-title">{icon("filter", 18)}수집 개수</div>')
        count = st.selectbox(
            "리뷰 수",
            options=[10, 20, 30, 50, 100, 150, 200, 300, 500],
            index=4,
            format_func=lambda x: f"{x:,} 건",
            label_visibility="collapsed", key="nv_count",
        )
    with col_b:
        html(f'<div class="card-title">{icon("sort", 18)}정렬</div>')
        sort_label = st.selectbox(
            "정렬 방식",
            options=["랭킹순", "최신순", "별점 높은순", "별점 낮은순"],
            index=0, label_visibility="collapsed", key="nv_sort",
        )

    html('<div style="height:18px;"></div>')
    text_only = st.checkbox(
        "본문 있는 후기만 수집  ·  별점만 누른 리뷰 제외",
        value=True, key="nv_text_only",
    )

    html(f"""
<div class="notice">
{icon("info", 18)}
<span>스마트스토어 / 브랜드스토어 상품 URL을 지원합니다. 요청 간 약 1초 지연.</span>
</div>
""")

    html('<div style="height:24px;"></div>')
    if st.button("후기 추출 시작", type="primary", key="nv_btn"):
        if not url.strip():
            _show_error("네이버 상품 URL을 입력해주세요.")
        else:
            try:
                parse_naver_url(url)
            except ValueError as e:
                _show_error(str(e))
                st.stop()

            progress = st.progress(0, text="리뷰 수집 준비 중…")

            def on_progress(current: int, total: int) -> None:
                ratio = min(current / total, 1.0)
                progress.progress(ratio, text=f"수집 중 · {current} / {total}")

            try:
                reviews, product_no = crawl_naver_reviews(
                    url=url,
                    max_count=count,
                    sort_label=sort_label,
                    delay=1.0,
                    text_only=text_only,
                    progress_cb=on_progress,
                )
            except PermissionError as e:
                progress.empty()
                _show_error(str(e))
                st.stop()
            except Exception as e:
                progress.empty()
                _show_error(f"수집 실패 · {type(e).__name__}: {e}")
                st.stop()

            progress.empty()

            if not reviews:
                _show_info("수집된 리뷰가 없습니다. 정렬을 바꿔보거나 다른 상품을 시도해 보세요.")
            else:
                raw = pd.DataFrame(reviews)
                df = pd.DataFrame({
                    "순서": range(1, len(raw) + 1),
                    "닉네임": raw["nickname"],
                    "작성일": raw["date"],
                    "옵션": raw["option"],
                    "후기": raw["content"],
                })
                st.session_state.nv_df = df
                st.session_state.nv_product_id = product_no

    df = st.session_state.nv_df
    if df is not None and not df.empty:
        html('<div style="height:48px;"></div>')

        total = len(df)
        with_text = int((df["후기"].astype(str).str.len() > 0).sum())
        unique_options = df["옵션"].nunique()

        html(f"""
<div class="metric-grid" style="grid-template-columns: repeat(3, 1fr);">
<div class="metric">
<div class="metric-label">{icon("table", 14)}수집 리뷰</div>
<div class="metric-value">{total}<span class="unit">건</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("sparkle", 14)}내용 있는 후기</div>
<div class="metric-value">{with_text}<span class="unit">건</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("package", 14)}옵션 종류</div>
<div class="metric-value">{unique_options}<span class="unit">개</span></div>
</div>
</div>
""")

        html(f'<div class="card-title">{icon("table", 18)}리뷰 데이터</div>')

        rows_html = "".join(
            f"<tr><td class='c-no'>{r['순서']}</td>"
            f"<td class='c-name'>{_esc(r['닉네임'])}</td>"
            f"<td class='c-date'>{_esc(r['작성일'])}</td>"
            f"<td class='c-option'>{_esc(r['옵션'])}</td>"
            f"<td class='c-review'>{_esc(r['후기'])}</td></tr>"
            for _, r in df.iterrows()
        )
        html(f"""
<div class="review-table-wrap">
<table class="review-table">
<colgroup>
<col style="width: 64px;" />
<col style="width: 96px;" />
<col style="width: 110px;" />
<col style="width: 240px;" />
<col />
</colgroup>
<thead>
<tr><th>순서</th><th>닉네임</th><th>작성일</th><th>옵션</th><th>후기</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
""")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="reviews")
        buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        file_name = f"naver_reviews_{st.session_state.nv_product_id}_{timestamp}.xlsx"

        html('<div style="height:20px;"></div>')
        st.download_button(
            label="엑셀 일괄 다운로드  (.xlsx)",
            data=buffer,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="nv_dl",
        )


# ─────────────────────────────────────────────────────────────────
# 쿠팡 탭
# ─────────────────────────────────────────────────────────────────
def render_coupang() -> None:
    if "cp_df" not in st.session_state:
        st.session_state.cp_df = None
        st.session_state.cp_product_id = None

    html(f'<div class="card-title">{icon("link", 18)}쿠팡 상품 링크</div>')
    url = st.text_input(
        label="URL",
        label_visibility="collapsed",
        placeholder="https://www.coupang.com/vp/products/...",
        key="cp_url",
    )

    html('<div style="height:24px;"></div>')

    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        html(f'<div class="card-title">{icon("filter", 18)}수집 개수</div>')
        count = st.selectbox(
            "리뷰 수",
            options=[10, 20, 30, 50, 100, 150, 200, 300, 500],
            index=4,
            format_func=lambda x: f"{x:,} 건",
            label_visibility="collapsed", key="cp_count",
        )
    with col_b:
        html(f'<div class="card-title">{icon("sort", 18)}정렬</div>')
        sort_label = st.selectbox(
            "정렬 방식",
            options=["베스트순", "최신순"],
            index=0, label_visibility="collapsed", key="cp_sort",
        )

    html('<div style="height:18px;"></div>')
    text_only = st.checkbox(
        "본문 있는 후기만 수집  ·  별점만 누른 리뷰 제외",
        value=True, key="cp_text_only",
    )

    sort_map = {"최신순": "DATE_DESC", "베스트순": "ORDER_SCORE_ASC"}

    html(f"""
<div class="notice">
{icon("info", 18)}
<span>요청 간 약 1.2초 지연을 둡니다. 500개 수집 시 2~3분이 걸릴 수 있어요.</span>
</div>
""")

    html('<div style="height:24px;"></div>')
    if st.button("후기 추출 시작", type="primary", key="cp_btn"):
        if not url.strip():
            _show_error("상품 URL을 입력해주세요.")
        else:
            try:
                product_id, _, _ = parse_product_url(url)
            except ValueError as e:
                _show_error(str(e))
                st.stop()

            progress = st.progress(0, text="리뷰 수집 준비 중…")

            def on_progress(current: int, total: int) -> None:
                ratio = min(current / total, 1.0)
                progress.progress(ratio, text=f"수집 중 · {current} / {total}")

            try:
                reviews = crawl_reviews(
                    url=url,
                    max_count=count,
                    sort_by=sort_map[sort_label],
                    rating_filter="",
                    delay=1.2,
                    text_only=text_only,
                    progress_cb=on_progress,
                )
            except Exception as e:
                progress.empty()
                _show_error(f"수집 실패 · {type(e).__name__}: {e}")
                st.stop()

            progress.empty()

            if not reviews:
                _show_info("수집된 리뷰가 없습니다. 정렬을 바꿔 다시 시도해 보세요.")
            else:
                raw = pd.DataFrame(reviews)

                def _pick_review(row):
                    content = (row.get("content") or "").strip()
                    survey = (row.get("survey") or "").strip()
                    headline = (row.get("headline") or "").strip()
                    if content:
                        return f"{headline}\n{content}".strip() if headline else content
                    if survey:
                        return survey
                    return headline

                df = pd.DataFrame({
                    "순서": range(1, len(raw) + 1),
                    "닉네임": raw["nickname"],
                    "작성일": raw["date"],
                    "옵션": raw["option"],
                    "후기": raw.apply(_pick_review, axis=1),
                })
                st.session_state.cp_df = df
                st.session_state.cp_product_id = product_id

    df = st.session_state.cp_df
    if df is not None and not df.empty:
        html('<div style="height:48px;"></div>')

        total = len(df)
        with_text = int((df["후기"].astype(str).str.len() > 0).sum())
        unique_options = df["옵션"].nunique()

        html(f"""
<div class="metric-grid" style="grid-template-columns: repeat(3, 1fr);">
<div class="metric">
<div class="metric-label">{icon("table", 14)}수집 리뷰</div>
<div class="metric-value">{total}<span class="unit">건</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("sparkle", 14)}내용 있는 후기</div>
<div class="metric-value">{with_text}<span class="unit">건</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("package", 14)}옵션 종류</div>
<div class="metric-value">{unique_options}<span class="unit">개</span></div>
</div>
</div>
""")

        html(f'<div class="card-title">{icon("table", 18)}리뷰 데이터</div>')

        rows_html = "".join(
            f"<tr><td class='c-no'>{r['순서']}</td>"
            f"<td class='c-name'>{_esc(r['닉네임'])}</td>"
            f"<td class='c-date'>{_esc(r['작성일'])}</td>"
            f"<td class='c-option'>{_esc(r['옵션'])}</td>"
            f"<td class='c-review'>{_esc(r['후기'])}</td></tr>"
            for _, r in df.iterrows()
        )
        html(f"""
<div class="review-table-wrap">
<table class="review-table">
<colgroup>
<col style="width: 64px;" />
<col style="width: 96px;" />
<col style="width: 110px;" />
<col style="width: 240px;" />
<col />
</colgroup>
<thead>
<tr><th>순서</th><th>닉네임</th><th>작성일</th><th>옵션</th><th>후기</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
""")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="reviews")
        buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        file_name = f"coupang_reviews_{st.session_state.cp_product_id}_{timestamp}.xlsx"

        html('<div style="height:20px;"></div>')
        st.download_button(
            label="엑셀 일괄 다운로드  (.xlsx)",
            data=buffer,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="cp_dl",
        )


# ─────────────────────────────────────────────────────────────────
# 유튜브 탭
# ─────────────────────────────────────────────────────────────────
def render_youtube() -> None:
    if "yt_df" not in st.session_state:
        st.session_state.yt_df = None
        st.session_state.yt_meta = None
    if "yt_api_key" not in st.session_state:
        st.session_state.yt_api_key = ""

    html(f'<div class="card-title">{icon("key", 18)}YouTube Data API Key</div>')
    api_key = st.text_input(
        label="API Key",
        type="password",
        value=st.session_state.yt_api_key,
        placeholder="AIza... (Google Cloud Console에서 발급)",
        label_visibility="collapsed",
        key="yt_api_input",
    )
    st.session_state.yt_api_key = api_key

    html(f"""
<div class="notice">
{icon("info", 18)}
<span>Google Cloud Console → API 및 서비스 → 사용자 인증 정보에서 'YouTube Data API v3' 활성화 후 API 키를 발급하세요. 키는 이 세션에만 저장됩니다.</span>
</div>
""")

    html('<div style="height:24px;"></div>')
    html(f'<div class="card-title">{icon("play", 18)}유튜브 영상 링크</div>')
    url = st.text_input(
        label="Video URL",
        label_visibility="collapsed",
        placeholder="https://www.youtube.com/watch?v=...  또는  https://youtu.be/...",
        key="yt_url",
    )

    html('<div style="height:24px;"></div>')

    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        html(f'<div class="card-title">{icon("filter", 18)}수집 개수</div>')
        count = st.selectbox(
            "댓글 수",
            options=[10, 30, 50, 100, 200, 300, 500, 1000],
            index=3,
            format_func=lambda x: f"{x:,} 건",
            label_visibility="collapsed", key="yt_count",
        )
    with col_b:
        html(f'<div class="card-title">{icon("sort", 18)}정렬</div>')
        sort_label = st.selectbox(
            "정렬 방식",
            options=["추천순", "최신순"],
            index=0, label_visibility="collapsed", key="yt_sort",
        )

    html('<div style="height:18px;"></div>')
    include_replies = st.checkbox(
        "답글(대댓글)도 포함",
        value=True, key="yt_replies",
    )

    sort_map = {"추천순": "relevance", "최신순": "time"}

    html('<div style="height:24px;"></div>')
    if st.button("댓글 추출 시작", type="primary", key="yt_btn"):
        if not api_key.strip():
            _show_error("YouTube API Key를 입력해주세요.")
        elif not url.strip():
            _show_error("유튜브 영상 URL을 입력해주세요.")
        else:
            try:
                parse_video_id(url)
            except ValueError as e:
                _show_error(str(e))
                st.stop()

            progress = st.progress(0, text="댓글 수집 준비 중…")

            def on_progress(current: int, total: int) -> None:
                ratio = min(current / total, 1.0)
                progress.progress(ratio, text=f"수집 중 · {current} / {total}")

            try:
                comments, meta = crawl_youtube_comments(
                    url=url,
                    api_key=api_key,
                    max_count=count,
                    order=sort_map[sort_label],
                    include_replies=include_replies,
                    progress_cb=on_progress,
                )
            except PermissionError as e:
                progress.empty()
                _show_error(str(e))
                st.stop()
            except Exception as e:
                progress.empty()
                _show_error(f"수집 실패 · {type(e).__name__}: {e}")
                st.stop()

            progress.empty()

            if not comments:
                _show_info("수집된 댓글이 없습니다. 댓글 사용이 중지되었거나 비공개 영상일 수 있어요.")
            else:
                raw = pd.DataFrame(comments)
                df = pd.DataFrame({
                    "순서": range(1, len(raw) + 1),
                    "구분": raw["is_reply"].map(lambda x: "답글" if x else "댓글"),
                    "작성자": raw["author"],
                    "작성일": raw["published_at"],
                    "좋아요": raw["like_count"].astype(int),
                    "답글수": raw["reply_count"].astype(int),
                    "댓글": raw["content"],
                })
                st.session_state.yt_df = df
                st.session_state.yt_meta = meta

    df = st.session_state.yt_df
    meta = st.session_state.yt_meta
    if df is not None and not df.empty:
        html('<div style="height:48px;"></div>')

        if meta and meta.get("title"):
            html(f"""
<div class="video-meta">
{icon("play", 22)}
<div class="video-meta-text">
<div class="video-meta-title">{_esc(meta.get('title', ''))}</div>
<div class="video-meta-channel">{_esc(meta.get('channel', ''))} · 전체 댓글 {int(meta.get('comment_count', 0)):,}개</div>
</div>
</div>
""")

        total = len(df)
        replies = int((df["구분"] == "답글").sum())
        likes_sum = int(df["좋아요"].sum())

        html(f"""
<div class="metric-grid" style="grid-template-columns: repeat(3, 1fr);">
<div class="metric">
<div class="metric-label">{icon("message", 14)}수집 댓글</div>
<div class="metric-value">{total}<span class="unit">건</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("users", 14)}답글</div>
<div class="metric-value">{replies}<span class="unit">건</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("heart", 14)}총 좋아요</div>
<div class="metric-value">{likes_sum:,}<span class="unit"></span></div>
</div>
</div>
""")

        html(f'<div class="card-title">{icon("table", 18)}댓글 데이터</div>')

        rows_html = "".join(
            f"<tr>"
            f"<td class='c-no'>{r['순서']}</td>"
            f"<td><span class='c-tag {'reply' if r['구분'] == '답글' else ''}'>{_esc(r['구분'])}</span></td>"
            f"<td class='c-name'>{_esc(r['작성자'])}</td>"
            f"<td class='c-date'>{_esc(r['작성일'])}</td>"
            f"<td class='c-num'>{int(r['좋아요']):,}</td>"
            f"<td class='c-num'>{int(r['답글수']):,}</td>"
            f"<td class='c-review'>{_esc(r['댓글'])}</td>"
            f"</tr>"
            for _, r in df.iterrows()
        )
        html(f"""
<div class="review-table-wrap">
<table class="review-table">
<colgroup>
<col style="width: 64px;" />
<col style="width: 78px;" />
<col style="width: 150px;" />
<col style="width: 110px;" />
<col style="width: 86px;" />
<col style="width: 86px;" />
<col />
</colgroup>
<thead>
<tr><th>순서</th><th>구분</th><th>작성자</th><th>작성일</th><th>좋아요</th><th>답글수</th><th>댓글</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>
""")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="comments")
        buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        video_id = (meta or {}).get("video_id", "video")
        file_name = f"youtube_comments_{video_id}_{timestamp}.xlsx"

        html('<div style="height:20px;"></div>')
        st.download_button(
            label="엑셀 일괄 다운로드  (.xlsx)",
            data=buffer,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="yt_dl",
        )


# ─────────────────────────────────────────────────────────────────
# Trends 탭 (검색어로 알고리즘 노출 영상/채널 발굴)
# ─────────────────────────────────────────────────────────────────
def _score_class(score: float) -> str:
    if score >= 10:
        return "s-fire"
    if score >= 3:
        return "s-high"
    if score >= 1:
        return "s-mid"
    return "s-low"


def render_trends() -> None:
    if "tr_results" not in st.session_state:
        st.session_state.tr_results = None
        st.session_state.tr_query = ""
    if "yt_api_key" not in st.session_state:
        st.session_state.yt_api_key = ""

    html(f'<div class="card-title">{icon("key", 18)}YouTube Data API Key</div>')
    api_key = st.text_input(
        label="API Key (Trends)",
        type="password",
        value=st.session_state.yt_api_key,
        placeholder="YouTube 탭과 동일한 키를 사용해도 됩니다",
        label_visibility="collapsed",
        key="tr_api_input",
    )
    st.session_state.yt_api_key = api_key

    html('<div style="height:24px;"></div>')

    html(f'<div class="card-title">{icon("search", 18)}검색어</div>')
    query = st.text_input(
        label="Query",
        label_visibility="collapsed",
        placeholder="예) 재테크 / 자취 브이로그 / AI 자동화",
        key="tr_query_input",
    )

    html('<div style="height:24px;"></div>')

    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    with col1:
        html(f'<div class="card-title">{icon("clock", 18)}기간</div>')
        period_label = st.selectbox(
            "기간",
            options=["최근 1일", "최근 7일", "최근 30일", "최근 90일", "최근 1년"],
            index=1, label_visibility="collapsed", key="tr_period",
        )
    with col2:
        html(f'<div class="card-title">{icon("sort", 18)}정렬</div>')
        order_label = st.selectbox(
            "정렬 방식",
            options=["관련도", "조회순", "최신순"],
            index=0, label_visibility="collapsed", key="tr_order",
        )
    with col3:
        html(f'<div class="card-title">{icon("play", 18)}영상 길이</div>')
        duration_label = st.selectbox(
            "영상 길이",
            options=["전체", "Shorts (4분 미만)", "일반 (4~20분)", "롱폼 (20분+)"],
            index=0, label_visibility="collapsed", key="tr_duration",
        )

    html('<div style="height:18px;"></div>')

    col4, col5, col6 = st.columns([1, 1, 1], gap="large")
    with col4:
        html(f'<div class="card-title">{icon("filter", 18)}최소 조회수</div>')
        min_views_label = st.selectbox(
            "최소 조회수",
            options=["제한 없음", "1만+", "5만+", "10만+", "50만+", "100만+"],
            index=1, label_visibility="collapsed", key="tr_minviews",
        )
    with col5:
        html(f'<div class="card-title">{icon("users", 18)}최대 구독자</div>')
        max_subs_label = st.selectbox(
            "최대 구독자수",
            options=["제한 없음", "10만 이하", "5만 이하", "1만 이하", "1천 이하"],
            index=0, label_visibility="collapsed", key="tr_maxsubs",
        )
    with col6:
        html(f'<div class="card-title">{icon("sparkle", 18)}최소 break-out</div>')
        min_breakout_label = st.selectbox(
            "최소 break-out",
            options=["제한 없음", "0.5+", "1.0+", "3.0+", "10.0+"],
            index=0, label_visibility="collapsed", key="tr_minbreakout",
        )

    html('<div style="height:18px;"></div>')
    html(f'<div class="card-title">{icon("filter", 18)}수집 영상 수</div>')
    max_count = st.selectbox(
        "수집 개수",
        options=[10, 20, 30, 50, 100, 150, 200],
        index=3,
        format_func=lambda x: f"{x:,} 개",
        label_visibility="collapsed", key="tr_count",
    )

    quota_cost = 100 * max(1, (max_count + 49) // 50) + 2 * max(1, (max_count + 49) // 50)

    period_map = {
        "최근 1일": 1, "최근 7일": 7, "최근 30일": 30,
        "최근 90일": 90, "최근 1년": 365,
    }
    min_views_map = {
        "제한 없음": 0, "1만+": 10_000, "5만+": 50_000,
        "10만+": 100_000, "50만+": 500_000, "100만+": 1_000_000,
    }
    max_subs_map = {
        "제한 없음": None, "10만 이하": 100_000, "5만 이하": 50_000,
        "1만 이하": 10_000, "1천 이하": 1_000,
    }
    min_breakout_map = {
        "제한 없음": 0.0, "0.5+": 0.5, "1.0+": 1.0,
        "3.0+": 3.0, "10.0+": 10.0,
    }

    html(f"""
<div class="notice split">
<div class="notice-main">
{icon("info", 18)}
<span><b>break-out 점수</b> = 영상 조회수 ÷ 채널 구독자수. <b>1.0 이상</b>이면 구독자 외부에서 조회 유입 = 추천 알고리즘 작동 중.</span>
</div>
<div class="quota-bar">{icon("sparkle", 13)}예상 쿼터 ≈ {quota_cost} / 10,000</div>
</div>
""")

    html('<div style="height:24px;"></div>')
    if st.button("트렌드 검색 시작", type="primary", key="tr_btn"):
        if not (api_key or "").strip():
            _show_error("YouTube API Key를 입력해주세요.")
        elif not (query or "").strip():
            _show_error("검색어를 입력해주세요.")
        else:
            progress = st.progress(0, text="검색 준비 중…")

            def on_progress(current: int, total: int, label: str) -> None:
                ratio = min(current / max(total, 1), 1.0)
                progress.progress(ratio, text=f"{label}  ·  {current} / {total}")

            try:
                results = search_trends(
                    api_key=api_key,
                    query=query,
                    days_ago=period_map[period_label],
                    order_label=order_label,
                    duration_label=duration_label,
                    region="KR",
                    min_views=min_views_map[min_views_label],
                    max_subscribers=max_subs_map[max_subs_label],
                    min_breakout=min_breakout_map[min_breakout_label],
                    max_count=max_count,
                    progress_cb=on_progress,
                )
            except (PermissionError, ValueError) as e:
                progress.empty()
                _show_error(str(e))
                st.stop()
            except Exception as e:
                progress.empty()
                _show_error(f"검색 실패 · {type(e).__name__}: {e}")
                st.stop()

            progress.empty()

            if not results:
                _show_info("조건에 맞는 영상이 없습니다. 필터를 완화하거나 기간을 늘려 보세요.")
                st.session_state.tr_results = None
            else:
                st.session_state.tr_results = pd.DataFrame(results)
                st.session_state.tr_query = query

    df = st.session_state.tr_results
    if df is not None and not df.empty:
        html('<div style="height:48px;"></div>')

        total = len(df)
        avg_breakout = round(df["breakout_score"].mean(), 2)
        unique_channels = df["channel_id"].nunique()
        hot_count = int((df["breakout_score"] >= 1.0).sum())

        html(f"""
<div class="metric-grid" style="grid-template-columns: repeat(4, 1fr);">
<div class="metric">
<div class="metric-label">{icon("table", 14)}수집 영상</div>
<div class="metric-value">{total}<span class="unit">개</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("users", 14)}고유 채널</div>
<div class="metric-value">{unique_channels}<span class="unit">곳</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("sparkle", 14)}평균 break-out</div>
<div class="metric-value">{avg_breakout}<span class="unit">×</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("sparkle", 14)}알고리즘 작동</div>
<div class="metric-value">{hot_count}<span class="unit">개</span></div>
</div>
</div>
""")

        html(f'<div class="card-title">{icon("table", 18)}트렌드 영상 (break-out 점수 내림차순)</div>')

        rows = []
        for i, r in enumerate(df.itertuples(), start=1):
            score_cls = _score_class(float(r.breakout_score))
            views_h = humanize(int(r.view_count))
            subs_h = humanize(int(r.subscriber_count))
            rows.append(
                f"<tr>"
                f"<td class='c-no'>{i}</td>"
                f"<td class='c-thumb'><a href='{_esc(r.video_url)}' target='_blank' rel='noopener'>"
                f"<img src='{_esc(r.thumbnail_url)}' loading='lazy' alt='' /></a></td>"
                f"<td class='c-title-cell'>"
                f"<a class='c-title-link' href='{_esc(r.video_url)}' target='_blank' rel='noopener'>{_esc(r.title)}</a>"
                f"<div class='c-meta'>{_esc(r.published_date)}  ·  {_esc(r.duration_text)}</div>"
                f"</td>"
                f"<td><div class='c-channel'>"
                f"<a class='c-channel-name' href='{_esc(r.channel_url)}' target='_blank' rel='noopener' style='text-decoration:none;'>{_esc(r.channel_title)}</a>"
                f"<span class='c-channel-subs'>구독자 {subs_h}</span>"
                f"</div></td>"
                f"<td class='c-num'><div class='c-stat'>{views_h}</div><div class='c-stat-sub'>{int(r.view_count):,}</div></td>"
                f"<td><span class='score-pill {score_cls}'>{r.breakout_score}×</span></td>"
                f"<td><span class='eng-pill'>{r.engagement_score}%</span></td>"
                f"</tr>"
            )

        html(f"""
<div class="review-table-wrap">
<table class="review-table">
<colgroup>
<col style="width: 52px;" />
<col style="width: 168px;" />
<col />
<col style="width: 180px;" />
<col style="width: 110px;" />
<col style="width: 92px;" />
<col style="width: 90px;" />
</colgroup>
<thead>
<tr><th>#</th><th>썸네일</th><th>제목</th><th>채널</th><th>조회수</th><th>break-out</th><th>참여도</th></tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
""")

        export_df = pd.DataFrame({
            "순서": range(1, len(df) + 1),
            "제목": df["title"],
            "영상링크": df["video_url"],
            "채널명": df["channel_title"],
            "채널링크": df["channel_url"],
            "구독자": df["subscriber_count"],
            "조회수": df["view_count"],
            "좋아요": df["like_count"],
            "댓글수": df["comment_count"],
            "break_out점수": df["breakout_score"],
            "참여도(%)": df["engagement_score"],
            "영상길이": df["duration_text"],
            "업로드일": df["published_date"],
            "썸네일": df["thumbnail_url"],
        })

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="trends")
        buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        safe_query = re.sub(r"[^\w\-]+", "_", st.session_state.tr_query)[:40] or "query"
        file_name = f"youtube_trends_{safe_query}_{timestamp}.xlsx"

        html('<div style="height:20px;"></div>')
        st.download_button(
            label="엑셀 일괄 다운로드  (.xlsx)",
            data=buffer,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="tr_dl",
        )


# ─────────────────────────────────────────────────────────────────
# News 탭 (이슈 빠른 파악 + 키워드 트렌드)
# ─────────────────────────────────────────────────────────────────
@st.dialog(" ", width="large")
def _show_news_modal() -> None:
    idx = st.session_state.get("ne_modal_idx")
    items = st.session_state.get("ne_items") or []
    if idx is None or idx >= len(items):
        st.warning("기사 정보를 불러올 수 없습니다.")
        return

    item = items[idx]

    # 헤더: eyebrow + 메타(언론사 칩 · 날짜) + 제목
    html(f"""
<div class="modal-eyebrow"><span class="modal-eyebrow-dot"></span>NEWS BRIEF</div>
<div class="modal-meta">
<span class="modal-chip">{_esc(item.get('source', ''))}</span>
<span class="modal-date">{_esc(item.get('published_at', ''))}</span>
</div>
<div class="modal-title">{_esc(item.get('title', ''))}</div>
""")

    # 본문 lazy fetch (세션 캐시)
    cache_key = f"_ne_full_{idx}"
    summ_key = f"_ne_summary_{idx}"
    if cache_key not in st.session_state:
        with st.spinner("본문을 불러와 요약 중…"):
            content = extract_article_content(item.get("url", ""))
            st.session_state[cache_key] = content
            st.session_state[summ_key] = summarize_text(content) if content else ""

    content = st.session_state.get(cache_key, "")
    summary = st.session_state.get(summ_key, "") or item.get("summary", "")

    if summary:
        html(f"""
<div class="modal-card">
<div class="modal-card-label">{icon("sparkle", 12)}핵심 요약</div>
<div class="modal-card-text">{_esc(summary)}</div>
</div>
""")
    else:
        html(f"""
<div class="modal-card warn">
<div class="modal-card-label">{icon("alert", 12)}알림</div>
<div class="modal-card-text">본문을 자동으로 가져오지 못했습니다. 아래 '원문 보기' 버튼으로 직접 확인해 주세요.</div>
</div>
""")

    if content:
        with st.expander("본문 전문 보기", expanded=False):
            html(f'<div class="modal-body-text">{_esc(content)}</div>')

    html('<div class="modal-footer-spacer"></div>')
    st.link_button("원문 보기 →", item.get("url", ""), use_container_width=True)


def render_news() -> None:
    if "ne_items" not in st.session_state:
        st.session_state.ne_items = None
        st.session_state.ne_keywords = None
        st.session_state.ne_query_label = ""

    html(f'<div class="card-title">{icon("search", 18)}모드</div>')
    mode = st.radio(
        "모드",
        options=["검색어", "카테고리"],
        horizontal=True,
        label_visibility="collapsed",
        key="ne_mode",
    )

    html('<div style="height:18px;"></div>')

    if mode == "검색어":
        html(f'<div class="card-title">{icon("search", 18)}검색어 (쉼표로 다중 키워드 가능)</div>')
        query_input = st.text_input(
            "검색어",
            label_visibility="collapsed",
            placeholder="예) 금리, AI 규제, 전기차",
            key="ne_query",
        )
        query = query_input
        query_label = query_input
    else:
        html(f'<div class="card-title">{icon("filter", 18)}카테고리</div>')
        category = st.selectbox(
            "카테고리",
            options=list(NEWS_CATEGORIES.keys()),
            index=1,
            label_visibility="collapsed",
            key="ne_category",
        )
        query = NEWS_CATEGORIES[category]
        query_label = category

    html('<div style="height:24px;"></div>')

    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    with col1:
        html(f'<div class="card-title">{icon("clock", 18)}기간</div>')
        period_label = st.selectbox(
            "기간",
            options=list(NEWS_PERIODS.keys()),
            index=2,
            label_visibility="collapsed",
            key="ne_period",
        )
    with col2:
        html(f'<div class="card-title">{icon("sort", 18)}정렬</div>')
        sort_label = st.selectbox(
            "정렬",
            options=["관련도", "최신순"],
            index=1,
            label_visibility="collapsed",
            key="ne_sort",
        )
    with col3:
        html(f'<div class="card-title">{icon("filter", 18)}수집 개수</div>')
        max_count = st.selectbox(
            "수집 개수",
            options=[20, 30, 50, 100, 150, 200],
            index=2,
            format_func=lambda x: f"{x:,} 건",
            label_visibility="collapsed",
            key="ne_count",
        )

    html('<div style="height:18px;"></div>')

    html(f'<div class="card-title">{icon("table", 18)}표시 모드</div>')
    display_mode = st.radio(
        "표시",
        options=["헤드라인", "요약형"],
        horizontal=True,
        label_visibility="collapsed",
        key="ne_display",
    )

    html(f"""
<div class="notice">
{icon("info", 18)}
<span>구글 뉴스 RSS 기반. 검색어에 <b>쉼표(,)</b>를 넣으면 여러 키워드를 동시에 검색해 합쳐줍니다.</span>
</div>
""")

    html('<div style="height:24px;"></div>')
    if st.button("뉴스 가져오기", type="primary", key="ne_btn"):
        if not (query or "").strip():
            _show_error("검색어 또는 카테고리를 선택해주세요.")
        else:
            progress = st.progress(0, text="뉴스 검색 중…")

            def on_progress(current: int, total: int) -> None:
                ratio = min(current / max(total, 1), 1.0)
                progress.progress(ratio, text=f"검색 중 · {current} / {total} 키워드")

            try:
                items, keywords = crawl_news(
                    query=query,
                    period_label=period_label,
                    sort_label=sort_label,
                    max_count=max_count,
                    progress_cb=on_progress,
                )
            except (ValueError, PermissionError) as e:
                progress.empty()
                _show_error(str(e))
                st.stop()
            except Exception as e:
                progress.empty()
                _show_error(f"수집 실패 · {type(e).__name__}: {e}")
                st.stop()

            progress.empty()

            if not items:
                _show_info("수집된 기사가 없습니다. 검색어나 기간을 바꿔보세요.")
                st.session_state.ne_items = None
            else:
                st.session_state.ne_items = items
                st.session_state.ne_keywords = keywords
                st.session_state.ne_query_label = query_label

    items = st.session_state.ne_items
    keywords = st.session_state.ne_keywords or []
    if items:
        html('<div style="height:48px;"></div>')

        total = len(items)
        unique_sources = len({it.get("source", "") for it in items if it.get("source")})
        top_kw_str = " · ".join([k for k, _ in keywords[:3]]) if keywords else "—"

        html(f"""
<div class="metric-grid" style="grid-template-columns: repeat(3, 1fr);">
<div class="metric">
<div class="metric-label">{icon("table", 14)}수집 기사</div>
<div class="metric-value">{total}<span class="unit">건</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("users", 14)}언론사</div>
<div class="metric-value">{unique_sources}<span class="unit">곳</span></div>
</div>
<div class="metric">
<div class="metric-label">{icon("sparkle", 14)}핵심 키워드</div>
<div class="metric-value" style="font-size:20px; line-height:1.35;">{_esc(top_kw_str)}</div>
</div>
</div>
""")

        if keywords:
            html(f'<div class="card-title">{icon("sparkle", 18)}TOP 키워드</div>')
            max_freq = max((c for _, c in keywords), default=1)
            kw_rows = "".join(
                f"<div class='kw-row'>"
                f"<span class='kw-name'>{_esc(name)}</span>"
                f"<div class='kw-bar-track'><div class='kw-bar-fill' style='width:{(count/max_freq)*100:.1f}%;'></div></div>"
                f"<span class='kw-count'>{count}</span>"
                f"</div>"
                for name, count in keywords
            )
            html(f"<div class='kw-chart'>{kw_rows}</div>")

        html(f'<div class="card-title">{icon("table", 18)}뉴스 목록</div>')

        if display_mode == "헤드라인":
            rows_html = "".join(
                f"<tr>"
                f"<td class='c-no'>{i}</td>"
                f"<td class='c-date'>{_esc(it.get('published_at',''))}</td>"
                f"<td class='c-source'>{_esc(it.get('source',''))}</td>"
                f"<td class='c-headline'>{_esc(it.get('title',''))}</td>"
                f"</tr>"
                for i, it in enumerate(items, start=1)
            )
            cols = (
                "<col style='width: 56px;' />"
                "<col style='width: 165px;' />"
                "<col style='width: 140px;' />"
                "<col />"
            )
            head = "<tr><th>#</th><th>발행시각</th><th>언론사</th><th>헤드라인</th></tr>"
        else:
            rows_html = "".join(
                f"<tr>"
                f"<td class='c-no'>{i}</td>"
                f"<td class='c-date'>{_esc(it.get('published_at',''))}</td>"
                f"<td class='c-source'>{_esc(it.get('source',''))}</td>"
                f"<td>"
                f"<div class='c-headline'>{_esc(it.get('title',''))}</div>"
                f"<div class='c-summary'>{_esc(it.get('summary',''))}</div>"
                f"</td>"
                f"</tr>"
                for i, it in enumerate(items, start=1)
            )
            cols = (
                "<col style='width: 56px;' />"
                "<col style='width: 165px;' />"
                "<col style='width: 140px;' />"
                "<col />"
            )
            head = "<tr><th>#</th><th>발행시각</th><th>언론사</th><th>제목 · 요약</th></tr>"

        html(f"""
<div class="review-table-wrap">
<table class="review-table news-table">
<colgroup>{cols}</colgroup>
<thead>{head}</thead>
<tbody>{rows_html}</tbody>
</table>
</div>
""")

        # ─── 기사 자세히 보기 (모달) ───
        html('<div style="height:20px;"></div>')
        html(f'<div class="card-title">{icon("search", 18)}기사 선택해서 요약 보기</div>')

        picker_col, btn_col = st.columns([4, 1], gap="medium")
        with picker_col:
            sel = st.selectbox(
                "기사 선택",
                options=list(range(len(items))),
                format_func=lambda i: f"{i+1}. {items[i].get('title','')[:80]}",
                index=None,
                placeholder="기사를 선택하세요…",
                label_visibility="collapsed",
                key="ne_picker",
            )
        with btn_col:
            open_modal = st.button(
                "요약 열기",
                disabled=(sel is None),
                key="ne_open_modal",
                use_container_width=True,
            )

        if open_modal and sel is not None:
            st.session_state.ne_modal_idx = sel
            _show_news_modal()

        export_df = pd.DataFrame({
            "순서": range(1, len(items) + 1),
            "발행시각": [it.get("published_at", "") for it in items],
            "언론사": [it.get("source", "") for it in items],
            "제목": [it.get("title", "") for it in items],
            "요약": [it.get("summary", "") for it in items],
            "원문URL": [it.get("url", "") for it in items],
        })

        if keywords:
            export_df["TOP키워드"] = ["; ".join(f"{k}({c})" for k, c in keywords)] + [""] * (len(items) - 1)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="news")
        buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        safe_label = re.sub(r"[^\w\-]+", "_", st.session_state.ne_query_label)[:30] or "news"
        file_name = f"news_{safe_label}_{timestamp}.xlsx"

        html('<div style="height:20px;"></div>')
        st.download_button(
            label="엑셀 일괄 다운로드  (.xlsx)",
            data=buffer,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="ne_dl",
        )


# ─────────────────────────────────────────────────────────────────
# 탭
# ─────────────────────────────────────────────────────────────────
tab_naver, tab_coupang, tab_youtube, tab_trends, tab_news = st.tabs(
    ["Naver", "Coupang", "YouTube", "Trends", "News"]
)
with tab_naver:
    render_naver()
with tab_coupang:
    render_coupang()
with tab_youtube:
    render_youtube()
with tab_trends:
    render_trends()
with tab_news:
    render_news()


# ─────────────────────────────────────────────────────────────────
# 푸터
# ─────────────────────────────────────────────────────────────────
html(f"""
<div class="footer">
<hr/>
{icon("clock", 12)} 본 도구는 개인 학습·분석 목적으로만 사용해 주세요.
</div>
""")
