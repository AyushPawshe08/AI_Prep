"""
AI Learning Pipeline — Streamlit frontend (v2 redesign)
=========================================================
Same backend contract as before: POST {api_base_url}/generate with
{"topic": <str>} against the existing FastAPI + LangGraph pipeline.
No backend, workflow, or state-handling logic is touched here — this
file only changes how the result is requested (still one blocking
POST call) and rendered.

Run:
    streamlit run app.py
"""

import io
import re
import time
import threading
import requests
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

# ==========================================================================
# CONSTANTS
# ==========================================================================

WORKFLOW_STEPS = [
    "Objectives",
    "Explanation",
    "Analogy",
    "Technical",
    "Code",
    "Quiz",
    "Revision",
]

# Roughly how long we let the fake-progress animation dwell on each step
# before advancing, while the real (single) API call is still in flight.
SECONDS_PER_STEP = 2.6

# ---- tiny inline icon set (line-style, currentColor) --------------------
ICONS = {
    "logo": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2 L21 7 L12 12 L3 7 Z"/><path d="M3 12 L12 17 L21 12"/><path d="M3 17 L12 22 L21 17"/>
        </svg>""",
    "target": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/>
        </svg>""",
    "book": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 5.5C4 4.7 4.7 4 5.5 4H12v16H5.5A1.5 1.5 0 0 1 4 18.5Z"/>
        <path d="M20 5.5c0-.8-.7-1.5-1.5-1.5H12v16h6.5a1.5 1.5 0 0 0 1.5-1.5Z"/>
        </svg>""",
    "quote": """<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <path d="M9.5 6C6.5 6 4 8.6 4 12v6h6.2v-6H7.3C7.3 9.9 8.6 8.4 10.7 8.1L9.5 6Z"/>
        <path d="M19 6c-3 0-5.5 2.6-5.5 6v6h6.2v-6h-2.9c0-2.1 1.3-3.6 3.4-3.9L19 6Z"/>
        </svg>""",
    "cpu": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="6" y="6" width="12" height="12" rx="1.5"/>
        <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>
        </svg>""",
    "terminal": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/>
        </svg>""",
    "help": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9"/>
        <path d="M9.5 9a2.5 2.5 0 0 1 4.6 1.3c0 1.7-2.1 2-2.1 3.3"/><path d="M12 17h.01"/>
        </svg>""",
    "sparkles": """<svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2l1.6 5.4L19 9l-5.4 1.6L12 16l-1.6-5.4L5 9l5.4-1.6L12 2Z"/>
        <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/>
        </svg>""",
    "check": """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 6 9 17l-5-5"/></svg>""",
    "arrow": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M5 12h14M13 5l7 7-7 7"/></svg>""",
    "github": """<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.46-1.15-1.11-1.46-1.11-1.46-.9-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.9 1.52 2.34 1.08 2.91.83.09-.65.35-1.08.63-1.33-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.65 0 0 .84-.27 2.75 1.02a9.6 9.6 0 0 1 5 0c1.9-1.29 2.74-1.02 2.74-1.02.56 1.38.21 2.4.1 2.65.65.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.75c0 .27.18.58.69.48A10 10 0 0 0 12 2Z"/>
        </svg>""",
    "revision": """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/>
        </svg>""",
}


def icon(name: str) -> str:
    return ICONS.get(name, "")


# ==========================================================================
# PAGE CONFIG
# ==========================================================================

st.set_page_config(
    page_title="AI Learning Pipeline",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================================================
# GLOBAL STYLE
# ==========================================================================

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --bg: #08090C;
            --card: #111318;
            --card-2: #15171D;
            --border: #262A33;
            --yellow: #F5C542;
            --yellow-hover: #FFD75A;
            --text: #F5F5F0;
            --text-secondary: #9A9DA7;
            --text-muted: #686C76;
            --radius-lg: 20px;
            --radius-md: 16px;
            --radius-sm: 10px;
        }

        html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

        #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }

        .stApp {
            background: var(--bg);
            background-image:
                radial-gradient(560px 320px at 50% -6%, rgba(245,197,66,0.10), transparent 60%),
                radial-gradient(circle at 12% 18%, rgba(245,197,66,0.035) 0, transparent 40%),
                radial-gradient(circle at 88% 78%, rgba(245,197,66,0.03) 0, transparent 40%);
        }

        /* centered app shell */
        .main .block-container {
            max-width: 1140px;
            padding-top: 0.6rem;
            padding-bottom: 3rem;
            margin: 0 auto;
        }

        section[data-testid="stSidebar"] {
            background: #0b0c11;
            border-right: 1px solid var(--border);
        }
        section[data-testid="stSidebar"] * { color: var(--text) !important; }
        section[data-testid="stSidebar"] input {
            background: var(--card) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
        }

        /* ---------------- NAVBAR ---------------- */
        .navbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1.1rem 0.2rem;
            border-bottom: 1px solid var(--border);
            margin-bottom: 2.4rem;
        }
        .navbar-brand {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            font-weight: 700;
            font-size: 0.98rem;
            color: var(--text);
            letter-spacing: -0.01em;
        }
        .navbar-brand .brand-icon {
            width: 30px; height: 30px;
            display: flex; align-items: center; justify-content: center;
            background: var(--yellow);
            color: #08090C;
            border-radius: 8px;
        }
        .navbar-links {
            display: flex;
            align-items: center;
            gap: 1.6rem;
        }
        .navbar-links a {
            color: var(--text-secondary);
            font-size: 0.86rem;
            font-weight: 500;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.4rem;
            transition: color .15s ease;
        }
        .navbar-links a:hover { color: var(--text); }
        .status-chip {
            display: flex; align-items: center; gap: 0.4rem;
            font-size: 0.78rem; font-weight: 600; color: var(--text-secondary);
            border: 1px solid var(--border); padding: 0.3rem 0.65rem; border-radius: 999px;
        }
        .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--yellow);
            box-shadow: 0 0 0 3px rgba(245,197,66,0.16); }

        /* ---------------- HERO ---------------- */
        .hero { text-align: center; padding: 1.4rem 0 2.2rem 0; animation: fadeUp .5s ease both; }
        .eyebrow {
            display: inline-flex; align-items: center; gap: 0.4rem;
            font-size: 0.72rem; font-weight: 700; letter-spacing: 0.16em;
            text-transform: uppercase; color: var(--yellow);
            background: rgba(245,197,66,0.09);
            border: 1px solid rgba(245,197,66,0.25);
            padding: 0.35rem 0.85rem; border-radius: 999px;
            margin-bottom: 1.3rem;
        }
        .hero h1 {
            font-size: 3.2rem;
            line-height: 1.08;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: var(--text);
            margin: 0 0 1.1rem 0;
        }
        .hero h1 .accent { color: var(--yellow); }
        .hero p.sub {
            max-width: 620px;
            margin: 0 auto;
            color: var(--text-secondary);
            font-size: 1.05rem;
            line-height: 1.6;
        }

        /* ---------------- INPUT CARD ---------------- */
        .input-shell {
            max-width: 760px;
            margin: 2.2rem auto 1.2rem auto;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.7rem 1.9rem 1.5rem 1.9rem;
            animation: fadeUp .55s ease both;
            animation-delay: .05s;
        }
        .input-label {
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 0.55rem;
        }
        div[data-testid="stTextInput"] input {
            background: #0c0e13 !important;
            border: 1px solid var(--border) !important;
            color: var(--text) !important;
            border-radius: 12px !important;
            padding: 0.85rem 1rem !important;
            font-size: 1rem !important;
            height: 3.1rem !important;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: var(--yellow) !important;
            box-shadow: 0 0 0 1px var(--yellow) !important;
        }
        div[data-testid="stTextInput"] input::placeholder { color: var(--text-muted) !important; }

        div.stButton > button {
            background: var(--yellow);
            color: #0a0a0a;
            border: none;
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.92rem;
            padding: 0.72rem 1.3rem;
            width: 100%;
            height: 3.1rem;
            transition: transform .12s ease, background .12s ease, box-shadow .12s ease;
            box-shadow: 0 0 0 rgba(245,197,66,0);
        }
        div.stButton > button:hover {
            background: var(--yellow-hover);
            transform: translateY(-2px);
            box-shadow: 0 10px 24px -10px rgba(245,197,66,0.55);
        }
        div.stButton > button:active { transform: translateY(0px); }
        div.stButton > button:disabled {
            background: #3a3a33; color: #8a8a80; transform:none; box-shadow:none;
        }

        /* secondary / download button */
        div[data-testid="stDownloadButton"] > button {
            background: transparent;
            color: var(--yellow);
            border: 1px solid rgba(245,197,66,0.45);
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.86rem;
            padding: 0.6rem 1rem;
            width: 100%;
            transition: all .15s ease;
        }
        div[data-testid="stDownloadButton"] > button:hover {
            background: rgba(245,197,66,0.08);
            border-color: var(--yellow);
            transform: translateY(-1px);
        }
        .pdf-btn-row { max-width: 320px; margin: 0 auto 1.6rem auto; }

        /* ---------------- WORKFLOW BAR ---------------- */
        .workflow-wrap {
            max-width: 900px;
            margin: 1.6rem auto 0 auto;
            overflow-x: auto;
            padding-bottom: 0.3rem;
        }
        .workflow-row {
            display: flex;
            align-items: flex-start;
            justify-content: center;
            gap: 0;
            min-width: 620px;
        }
        .wf-step { display: flex; flex-direction: column; align-items: center; width: 100px; flex-shrink: 0; }
        .wf-circle {
            width: 34px; height: 34px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.78rem; font-weight: 700;
            border: 1.5px solid var(--border);
            color: var(--text-muted);
            background: var(--card);
            transition: all .25s ease;
        }
        .wf-circle.active {
            border-color: var(--yellow);
            color: #0a0a0a;
            background: var(--yellow);
            box-shadow: 0 0 0 5px rgba(245,197,66,0.14);
            animation: pulse 1.4s ease-in-out infinite;
        }
        .wf-circle.done {
            border-color: var(--yellow);
            color: var(--yellow);
            background: rgba(245,197,66,0.1);
        }
        .wf-label {
            font-size: 0.72rem; font-weight: 600; color: var(--text-muted);
            margin-top: 0.5rem; text-align: center; letter-spacing: 0.01em;
        }
        .wf-label.on { color: var(--text); }
        .wf-connector {
            flex: 1; height: 1.5px; background: var(--border);
            margin-top: 17px; min-width: 14px; transition: background .3s ease;
        }
        .wf-connector.done { background: var(--yellow); }

        /* ---------------- LOADING PANEL ---------------- */
        .loading-shell {
            max-width: 480px;
            margin: 1.6rem auto 0 auto;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 1.3rem 1.5rem;
        }
        .loading-title {
            font-weight: 700; font-size: 0.95rem; color: var(--text);
            margin-bottom: 0.9rem; display:flex; align-items:center; gap:0.5rem;
        }
        .loading-item { display: flex; align-items: center; gap: 0.65rem; padding: 0.32rem 0; font-size: 0.87rem; }
        .loading-item .mark { width: 16px; text-align: center; font-weight: 700; }
        .loading-item.done { color: var(--text-secondary); }
        .loading-item.done .mark { color: var(--yellow); }
        .loading-item.active { color: var(--text); }
        .loading-item.active .mark { color: var(--yellow); animation: blink 1s ease-in-out infinite; }
        .loading-item.pending { color: var(--text-muted); }
        .loading-item.pending .mark { color: var(--text-muted); }

        /* ---------------- RESULTS ---------------- */
        .results-header { text-align: center; margin: 2.6rem 0 2rem 0; animation: fadeUp .4s ease both; }
        .results-eyebrow {
            font-size: 0.75rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
            color: var(--text-muted); margin-bottom: 0.5rem;
        }
        .results-topic {
            font-size: 2rem; font-weight: 800; letter-spacing: -0.01em; color: var(--yellow);
            text-transform: uppercase; margin: 0;
        }
        .results-tagline { color: var(--text-secondary); font-size: 1rem; margin-top: 0.35rem; }

        .section-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 1.9rem 2rem;
            margin-bottom: 1.4rem;
            animation: fadeUp .4s ease both;
        }
        .section-card.alt { background: var(--card-2); }
        .section-card.quote-card { position: relative; background: var(--card-2); border-color: #302a1c; }

        .section-heading {
            display: flex; align-items: center; gap: 0.65rem;
            margin-bottom: 1.25rem;
        }
        .section-heading .ic {
            width: 34px; height: 34px; border-radius: 9px;
            background: rgba(245,197,66,0.1); color: var(--yellow);
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .section-heading .heading-text { display: flex; flex-direction: column; }
        .section-heading .kicker {
            font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
            color: var(--yellow); margin-bottom: 0.1rem;
        }
        .section-heading h3 {
            font-size: 1.28rem; font-weight: 700; color: var(--text); margin: 0; letter-spacing: -0.01em;
        }

        .obj-item {
            display: flex; align-items: flex-start; gap: 0.9rem;
            padding: 0.7rem 0; border-bottom: 1px solid var(--border);
        }
        .obj-item:last-child { border-bottom: none; }
        .obj-num {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700; font-size: 0.85rem; color: var(--yellow);
            flex-shrink: 0; width: 28px; padding-top: 0.15rem;
        }
        .obj-text { color: var(--text); font-size: 0.96rem; line-height: 1.55; }

        .prose, .prose p, .prose li { color: var(--text); font-size: 0.97rem; line-height: 1.75; }
        .prose h1, .prose h2, .prose h3, .prose h4 { color: var(--text); font-weight: 700; letter-spacing: -0.01em; }
        .prose h2 { font-size: 1.15rem; margin-top: 1.4rem; }
        .prose h3 { font-size: 1.05rem; margin-top: 1.2rem; }
        .prose table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.86rem; }
        .prose th, .prose td { border: 1px solid var(--border); padding: 0.55rem 0.75rem; text-align: left; }
        .prose th { background: #1a1c24; color: var(--text); font-weight: 600; }
        .prose td { color: var(--text-secondary); }
        .prose code {
            background: rgba(245,197,66,0.08); color: var(--yellow);
            padding: 0.12rem 0.4rem; border-radius: 5px;
            font-family: 'JetBrains Mono', monospace; font-size: 0.86em;
        }
        .prose blockquote {
            border-left: 3px solid var(--yellow);
            margin: 0.8rem 0; padding: 0.2rem 0 0.2rem 1rem;
            color: var(--text-secondary); font-style: italic;
        }
        .prose hr { border-color: var(--border); }

        .quote-mark { position: absolute; top: 1.1rem; right: 1.5rem; color: rgba(245,197,66,0.25); }

        .badge-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.9rem; }
        .term-badge {
            font-size: 0.78rem; font-weight: 600; color: var(--yellow);
            background: rgba(245,197,66,0.08); border: 1px solid rgba(245,197,66,0.22);
            padding: 0.28rem 0.7rem; border-radius: 999px;
        }

        .code-label-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.7rem; }
        .code-lang-pill {
            font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; font-weight: 600;
            color: var(--text-secondary); background: #1a1c24; border: 1px solid var(--border);
            padding: 0.22rem 0.65rem; border-radius: 6px;
        }
        div[data-testid="stCodeBlock"] pre {
            border-radius: 14px !important;
            border: 1px solid var(--border) !important;
        }

        .quiz-card {
            background: var(--card-2);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 1.3rem 1.5rem;
            margin-bottom: 1rem;
        }
        .quiz-tag {
            font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em; color: var(--yellow);
            text-transform: uppercase; margin-bottom: 0.55rem;
        }
        .quiz-question { color: var(--text); font-size: 1rem; font-weight: 600; margin-bottom: 0.9rem; line-height: 1.5; }
        div[data-testid="stRadio"] label { color: var(--text) !important; font-size: 0.92rem !important; }
        div[data-testid="stRadio"] > div { gap: 0.4rem !important; }

        .result-pill {
            display: inline-flex; align-items: center; gap: 0.4rem;
            font-size: 0.82rem; font-weight: 700; padding: 0.35rem 0.8rem; border-radius: 999px;
            margin-top: 0.7rem;
        }
        .result-pill.correct { color: #08090C; background: var(--yellow); }
        .result-pill.incorrect { color: var(--text); background: #2a1414; border: 1px solid #5a2626; }
        .result-pill.neutral { color: var(--text-secondary); background: #1a1c24; border: 1px solid var(--border); }

        .revision-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 0.8rem; margin-top: 0.3rem; }
        .revision-item {
            background: #0e1015; border: 1px solid var(--border); border-radius: 14px;
            padding: 1rem 1.1rem;
        }
        .revision-item .rterm { color: var(--yellow); font-weight: 700; font-size: 0.92rem; margin-bottom: 0.35rem; }
        .revision-item .rdef { color: var(--text-secondary); font-size: 0.85rem; line-height: 1.5; }

        .final-cta {
            text-align: center; margin-top: 2.6rem; padding: 2.4rem 1.5rem;
            border: 1px dashed var(--border); border-radius: var(--radius-lg);
        }
        .final-cta h4 { color: var(--text); font-size: 1.2rem; font-weight: 700; margin-bottom: 1.1rem; }
        .final-cta-btn { max-width: 320px; margin: 0 auto; }

        ::-webkit-scrollbar { height: 6px; width: 6px; }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 6px; }

        @keyframes fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { box-shadow: 0 0 0 5px rgba(245,197,66,0.14); } 50% { box-shadow: 0 0 0 9px rgba(245,197,66,0.06); } }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

        @media (max-width: 900px) {
            .hero h1 { font-size: 2.3rem; }
            .section-card { padding: 1.4rem 1.3rem; }
        }
        @media (max-width: 640px) {
            .hero h1 { font-size: 1.9rem; }
            .hero p.sub { font-size: 0.95rem; }
            .navbar-links a span.link-text { display: none; }
            .input-shell { padding: 1.2rem; }
            .revision-grid { grid-template-columns: 1fr; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================================================
# SIDEBAR — connection settings (kept, restyled, collapsed by default)
# ==========================================================================

with st.sidebar:
    st.markdown("**Pipeline settings**")
    api_base_url = st.text_input(
        "API base URL",
        value=st.session_state.get("api_base_url", "http://localhost:8000"),
    )
    st.session_state["api_base_url"] = api_base_url
    request_timeout = st.slider("Request timeout (seconds)", 30, 300, 120, step=10)
    st.caption("Calls POST /generate on the existing FastAPI + LangGraph backend. No backend logic is modified here.")

# ==========================================================================
# NAVBAR
# ==========================================================================

st.markdown(
    f"""
    <div class="navbar">
        <div class="navbar-brand">
            <div class="brand-icon">{icon('logo')}</div>
            AI Learning Pipeline
        </div>
        <div class="navbar-links">
            <a href="#how-it-works">{icon('help')}<span class="link-text">How it works</span></a>
            <a href="https://github.com" target="_blank">{icon('github')}<span class="link-text">GitHub</span></a>
            <div class="status-chip"><span class="status-dot"></span>Backend ready</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==========================================================================
# HELPERS
# ==========================================================================


def call_backend(topic: str, base_url: str, timeout: int, holder: dict) -> None:
    """Runs in a background thread; identical request to before."""
    try:
        resp = requests.post(f"{base_url.rstrip('/')}/generate", json={"topic": topic}, timeout=timeout)
        resp.raise_for_status()
        holder["data"] = resp.json()
    except requests.exceptions.ConnectionError:
        holder["error"] = f"Could not reach the API at {base_url}. Confirm the FastAPI server is running."
    except requests.exceptions.Timeout:
        holder["error"] = "The request timed out. Try increasing the timeout in the sidebar."
    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            pass
        holder["error"] = f"API returned an error: {e}. {detail}"
    except Exception as e:
        holder["error"] = f"Unexpected error: {e}"


def render_workflow_bar(active_idx: int, mode: str = "idle") -> str:
    """mode: 'idle' | 'running' | 'done'. active_idx is the step currently running."""
    steps_html = []
    n = len(WORKFLOW_STEPS)
    for i, label in enumerate(WORKFLOW_STEPS):
        if mode == "done" or (mode == "running" and i < active_idx):
            circle_cls, label_cls, content = "done", "on", icon("check")
        elif mode == "running" and i == active_idx:
            circle_cls, label_cls, content = "active", "on", str(i + 1).zfill(2)
        else:
            circle_cls, label_cls, content = "", "", str(i + 1).zfill(2)

        steps_html.append(
            f'<div class="wf-step">'
            f'<div class="wf-circle {circle_cls}">{content}</div>'
            f'<div class="wf-label {label_cls}">{label}</div>'
            f"</div>"
        )
        if i < n - 1:
            connector_done = "done" if (mode == "done" or (mode == "running" and i < active_idx)) else ""
            steps_html.append(f'<div class="wf-connector {connector_done}"></div>')

    return f'<div class="workflow-wrap"><div class="workflow-row">{"".join(steps_html)}</div></div>'


LOADING_LABELS = [
    "Generating learning objectives",
    "Creating explanation",
    "Creating analogy",
    "Generating technical explanation",
    "Creating code example",
    "Building quiz",
    "Preparing revision notes",
]


def render_loading_panel(active_idx: int) -> str:
    items = []
    for i, label in enumerate(LOADING_LABELS):
        if i < active_idx:
            items.append(f'<div class="loading-item done"><span class="mark">{icon("check")}</span>{label}</div>')
        elif i == active_idx:
            items.append(f'<div class="loading-item active"><span class="mark">&#9679;</span>{label}</div>')
        else:
            items.append(f'<div class="loading-item pending"><span class="mark">&#9675;</span>{label}</div>')
    return (
        '<div class="loading-shell">'
        f'<div class="loading-title">{icon("sparkles")}Building your learning module...</div>'
        + "".join(items)
        + "</div>"
    )


def strip_embedded_answer_key(quiz_text: str):
    """Splits the quiz field into (quiz_body, answer_key_text) if the model
    appended an 'Answer Key' section at the end, so we don't spoil answers
    before the user interacts with the quiz."""
    match = re.search(r"(?im)^#{1,4}\s*answer key.*$", quiz_text or "")
    if not match:
        return quiz_text, ""
    return quiz_text[: match.start()].strip(), quiz_text[match.start():].strip()


def parse_mcq_blocks(quiz_body: str):
    """Best-effort split of the quiz markdown into individual question
    blocks, each with an optional set of A/B/C/D options."""
    if not quiz_body:
        return []
    header_re = re.compile(r"(?im)^#{1,4}\s*question\s+\d+.*$")
    headers = list(header_re.finditer(quiz_body))
    blocks = []
    if headers:
        for idx, h in enumerate(headers):
            start = h.start()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(quiz_body)
            blocks.append(quiz_body[start:end].strip())
    else:
        blocks = [quiz_body.strip()]

    parsed = []
    option_re = re.compile(r"(?m)^\s*([A-D])[\.\)]\s+(.*)$")
    for block in blocks:
        options = option_re.findall(block)
        # strip options out of the prose so the question text stays clean
        prose = option_re.sub("", block).strip()
        parsed.append({"prose": prose, "options": options})
    return parsed


def parse_answer_letters(answer_key_text: str):
    """Extracts a {question_number: correct_letter} map from a section
    formatted like '**Q1:** **B** – ...' (the format the pipeline's own
    quiz prompt tends to produce)."""
    mapping = {}
    for m in re.finditer(r"\*\*Q(\d+):\*\*\s*\*\*([A-Za-z0-9]+)\*\*", answer_key_text or ""):
        mapping[int(m.group(1))] = m.group(2).strip().upper()
    return mapping


def extract_python_code(code_field: str):
    """Pulls the first fenced python block out of the code_example field,
    returning (code, remaining_markdown)."""
    if not code_field:
        return "", ""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", code_field, re.DOTALL)
    if not match:
        return "", code_field
    code = match.group(1).rstrip()
    remainder = (code_field[: match.start()] + code_field[match.end():]).strip()
    return code, remainder


def extract_terms(text: str, limit: int = 6):
    """Pulls a handful of bolded/backticked terms out of markdown to show
    as small highlight badges."""
    terms = re.findall(r"\*\*([A-Za-z][A-Za-z0-9 \-/]{2,28})\*\*", text or "")
    seen, out = set(), []
    for t in terms:
        key = t.strip().lower()
        if key not in seen:
            seen.add(key)
            out.append(t.strip())
        if len(out) >= limit:
            break
    return out


def parse_revision_items(revision_text: str, limit: int = 8):
    """Heuristically pulls short 'Term — definition' pairs out of the
    revision notes markdown (table rows or bold-term lines) for the badge
    grid; falls back gracefully if nothing matches."""
    items = []
    for row in re.finditer(r"\|\s*\*\*([^|*]{2,40})\*\*\s*\|\s*([^|]{2,140})\|", revision_text or ""):
        term = row.group(1).strip()
        definition = re.sub(r"[*`]", "", row.group(2)).strip()
        if term and definition and "---" not in term:
            items.append((term, definition))
    if not items:
        for row in re.finditer(r"(?m)^\*\*([^*\n]{2,40})\*\*\s*[-–—:]\s*(.{5,140})$", revision_text or ""):
            items.append((row.group(1).strip(), row.group(2).strip()))
    return items[:limit]


def _pdf_escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pdf_inline(text: str) -> str:
    """Converts a line of markdown (bold/italic/inline-code) into the
    small XML markup that reportlab's Paragraph understands."""
    text = _pdf_escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    return text


def _pdf_styles():
    base = getSampleStyleSheet()
    black = colors.black
    return {
        "DocTitle": ParagraphStyle("DocTitle", parent=base["Title"], textColor=black, fontSize=24, leading=28),
        "DocMeta": ParagraphStyle("DocMeta", parent=base["Normal"], textColor=colors.HexColor("#444444"), fontSize=9.5, leading=13),
        "SectionTitle": ParagraphStyle("SectionTitle", parent=base["Heading1"], textColor=black, fontSize=15, leading=19, spaceBefore=6, spaceAfter=8, fontName="Helvetica-Bold"),
        "H1": ParagraphStyle("H1", parent=base["Heading2"], textColor=black, fontSize=13, leading=16, spaceBefore=10, spaceAfter=5, fontName="Helvetica-Bold"),
        "H2": ParagraphStyle("H2", parent=base["Heading3"], textColor=black, fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold"),
        "H3": ParagraphStyle("H3", parent=base["Heading4"], textColor=black, fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=4, fontName="Helvetica-Bold"),
        "H4": ParagraphStyle("H4", parent=base["Heading4"], textColor=black, fontSize=10, leading=13, spaceBefore=5, spaceAfter=3, fontName="Helvetica-Bold"),
        "Body": ParagraphStyle("Body", parent=base["Normal"], textColor=black, fontSize=10.2, leading=15, fontName="Helvetica"),
        "Bullet": ParagraphStyle("Bullet", parent=base["Normal"], textColor=black, fontSize=10.2, leading=15, leftIndent=14, fontName="Helvetica"),
        "Code": ParagraphStyle("Code", parent=base["Normal"], textColor=black, fontSize=8.4, leading=11, fontName="Courier"),
        "TableCell": ParagraphStyle("TableCell", parent=base["Normal"], textColor=black, fontSize=8.8, leading=12, fontName="Helvetica"),
    }


def _markdown_to_flowables(md_text: str, styles: dict) -> list:
    """Best-effort conversion of the pipeline's markdown fields into
    reportlab flowables: headings, paragraphs, bullet/numbered lists,
    pipe tables, and fenced code blocks."""
    flowables = []
    if not (md_text and md_text.strip()):
        return flowables

    segments = re.split(r"(```[a-zA-Z]*\n.*?```)", md_text, flags=re.DOTALL)

    for seg in segments:
        if seg.startswith("```"):
            code = re.sub(r"^```[a-zA-Z]*\n", "", seg)
            code = re.sub(r"```$", "", code).rstrip("\n")
            flowables.append(Spacer(1, 4))
            flowables.append(Preformatted(code, styles["Code"]))
            flowables.append(Spacer(1, 8))
            continue

        buf: list = []
        table_buf: list = []

        def flush_buf():
            if buf:
                para_text = " ".join(buf).strip()
                if para_text:
                    flowables.append(Paragraph(_pdf_inline(para_text), styles["Body"]))
                    flowables.append(Spacer(1, 6))
                buf.clear()

        def flush_table():
            if table_buf:
                rows = []
                for r in table_buf:
                    cells = [c.strip() for c in r.strip().strip("|").split("|")]
                    if all(re.match(r"^:?-+:?$", c) for c in cells if c != ""):
                        continue
                    rows.append([Paragraph(_pdf_inline(c), styles["TableCell"]) for c in cells])
                if rows:
                    t = Table(rows, hAlign="LEFT")
                    t.setStyle(
                        TableStyle(
                            [
                                ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                                ("TOPPADDING", (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ]
                        )
                    )
                    flowables.append(t)
                    flowables.append(Spacer(1, 8))
                table_buf.clear()

        for line in seg.split("\n"):
            stripped = line.strip()

            if not stripped:
                flush_buf()
                flush_table()
                continue

            if stripped.count("|") >= 2:
                flush_buf()
                table_buf.append(stripped)
                continue
            else:
                flush_table()

            heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
            if heading:
                flush_buf()
                level = len(heading.group(1))
                style_name = {1: "H1", 2: "H2", 3: "H3", 4: "H4"}.get(level, "H4")
                flowables.append(Paragraph(_pdf_inline(heading.group(2)), styles[style_name]))
                continue

            if re.match(r"^[-*]\s+", stripped):
                flush_buf()
                item = re.sub(r"^[-*]\s+", "", stripped)
                flowables.append(Paragraph("&bull;&nbsp;&nbsp;" + _pdf_inline(item), styles["Bullet"]))
                continue

            numbered = re.match(r"^(\d+)[\.\)]\s+(.*)$", stripped)
            if numbered:
                flush_buf()
                flowables.append(
                    Paragraph(f"{numbered.group(1)}.&nbsp; " + _pdf_inline(numbered.group(2)), styles["Bullet"])
                )
                continue

            if re.match(r"^-{3,}$", stripped):
                flush_buf()
                flowables.append(Spacer(1, 4))
                continue

            buf.append(stripped)

        flush_buf()
        flush_table()

    return flowables


def build_pdf_bytes(result: dict, topic: str) -> bytes:
    """Renders every field from the pipeline's response into a single
    white-background, black-text PDF. Reuses the exact same result dict
    the on-screen sections read from — no backend or state changes."""
    styles = _pdf_styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        title=f"{topic} — Learning Module",
    )

    story = []
    story.append(Paragraph("AI Learning Module", styles["DocMeta"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(_pdf_inline(topic or "Untitled Topic"), styles["DocTitle"]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    story.append(Spacer(1, 14))

    sections = [
        ("01 — Learning Objectives", result.get("learning_objectives", "")),
        ("02 — Explanation", result.get("explanation", "")),
        ("03 — Analogy", result.get("analogy", "")),
        ("04 — Technical Explanation", result.get("technical_explanation", "")),
        ("05 — Code Example", result.get("code_example", "")),
        ("06 — Quiz", result.get("quiz", "")),
        ("07 — Answer Key", result.get("answers", "")),
        ("08 — Quick Revision", result.get("revision_notes", "")),
    ]

    for i, (title, content) in enumerate(sections):
        story.append(Paragraph(_pdf_inline(title), styles["SectionTitle"]))
        story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#999999")))
        story.append(Spacer(1, 8))
        story.extend(_markdown_to_flowables(content, styles))
        if i < len(sections) - 1:
            story.append(Spacer(1, 10))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(letter[0] / 2, 0.5 * inch, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def section_card_open(kicker: str, title: str, ic: str, extra_class: str = ""):
    st.markdown(
        f"""
        <div class="section-card {extra_class}">
            <div class="section-heading">
                <div class="ic">{icon(ic)}</div>
                <div class="heading-text">
                    <div class="kicker">{kicker}</div>
                    <h3>{title}</h3>
                </div>
            </div>
        """,
        unsafe_allow_html=True,
    )


def section_card_close():
    st.markdown("</div>", unsafe_allow_html=True)


# ==========================================================================
# SESSION STATE DEFAULTS
# ==========================================================================

st.session_state.setdefault("result", None)
st.session_state.setdefault("topic_used", "")
st.session_state.setdefault("elapsed", 0.0)
st.session_state.setdefault("quiz_selections", {})
st.session_state.setdefault("quiz_submitted", {})

# ==========================================================================
# VIEW: INPUT (only when there is no result yet, or after reset)
# ==========================================================================

show_input = st.session_state["result"] is None

if show_input:
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">AI-Powered Learning</div>
            <h1>Learn Anything.<br><span class="accent">Structured by AI.</span></h1>
            <p class="sub">Turn any topic into a complete learning module with objectives, explanations,
            analogies, code examples, quizzes, and revision notes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # st.markdown('<div class="input-shell">', unsafe_allow_html=True)
    st.markdown('<div class="input-label">What do you want to learn?</div>', unsafe_allow_html=True)
    topic = st.text_input(
        "Topic",
        placeholder="e.g. Transformers, Kubernetes networking, Bayesian inference...",
        label_visibility="collapsed",
        key="topic_input",
    )
    generate_clicked = st.button("Generate Learning Module", key="generate_btn")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f'<div id="how-it-works"></div>{render_workflow_bar(0, mode="idle")}',
        unsafe_allow_html=True,
    )

    if generate_clicked:
        if not topic or not topic.strip():
            st.warning("Enter a topic before generating.")
        else:
            holder = {}
            thread = threading.Thread(
                target=call_backend,
                args=(topic, api_base_url, request_timeout, holder),
                daemon=True,
            )
            start = time.time()
            thread.start()

            workflow_slot = st.empty()
            loading_slot = st.empty()

            while thread.is_alive():
                elapsed = time.time() - start
                active_idx = min(int(elapsed // SECONDS_PER_STEP), len(WORKFLOW_STEPS) - 1)
                workflow_slot.markdown(render_workflow_bar(active_idx, mode="running"), unsafe_allow_html=True)
                loading_slot.markdown(render_loading_panel(active_idx), unsafe_allow_html=True)
                time.sleep(0.3)

            thread.join()

            if "error" in holder:
                workflow_slot.markdown(render_workflow_bar(0, mode="idle"), unsafe_allow_html=True)
                loading_slot.empty()
                st.error(holder["error"])
            else:
                workflow_slot.markdown(render_workflow_bar(len(WORKFLOW_STEPS), mode="done"), unsafe_allow_html=True)
                loading_slot.markdown(render_loading_panel(len(LOADING_LABELS)), unsafe_allow_html=True)
                st.session_state["result"] = holder["data"]
                st.session_state["topic_used"] = topic
                st.session_state["elapsed"] = time.time() - start
                st.session_state["quiz_selections"] = {}
                st.session_state["quiz_submitted"] = {}
                time.sleep(0.5)
                st.rerun()

# ==========================================================================
# VIEW: RESULTS
# ==========================================================================

result = st.session_state["result"]

if result:
    topic_used = st.session_state.get("topic_used", "").strip()

    st.markdown(render_workflow_bar(len(WORKFLOW_STEPS), mode="done"), unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="results-header">
            <div class="results-eyebrow">Your Learning Module</div>
            <div class="results-topic">{topic_used.upper()}</div>
            <div class="results-tagline">Generated in {st.session_state.get('elapsed', 0):.1f}s across a 7-step sequential pipeline</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- PDF export --------------------------------------------------------
    st.markdown('<div class="pdf-btn-row">', unsafe_allow_html=True)
    pdf_bytes = build_pdf_bytes(result, topic_used or "Learning Module")
    safe_filename = re.sub(r"[^a-zA-Z0-9]+", "_", topic_used).strip("_").lower() or "learning_module"
    st.download_button(
        "Download as PDF",
        data=pdf_bytes,
        file_name=f"{safe_filename}.pdf",
        mime="application/pdf",
        use_container_width=True,
        key="pdf_download_btn",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # ---- Objectives ------------------------------------------------------
    section_card_open("01", "Learning Objectives", "target")
    objectives_raw = result.get("learning_objectives", "") or ""
    obj_lines = [
        re.sub(r"^\s*[\d]+[\.\)]\s*|\*\*|^\-\s*", "", l).strip()
        for l in objectives_raw.split("\n")
        if l.strip() and re.match(r"^\s*(\d+[\.\)]|\-|\*)", l.strip())
    ]
    if obj_lines:
        for i, item in enumerate(obj_lines, start=1):
            st.markdown(
                f'<div class="obj-item"><div class="obj-num">{str(i).zfill(2)}</div>'
                f'<div class="obj-text">{item}</div></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(f'<div class="prose">{objectives_raw}</div>', unsafe_allow_html=True)
    section_card_close()

    # ---- Explanation -------------------------------------------------------
    section_card_open("02", "Simple Explanation", "book")
    explanation_text = result.get("explanation", "") or "_No content returned._"
    st.markdown(f'<div class="prose">', unsafe_allow_html=True)
    st.markdown(explanation_text)
    st.markdown("</div>", unsafe_allow_html=True)
    terms = extract_terms(explanation_text)
    if terms:
        st.markdown(
            '<div class="badge-row">' + "".join(f'<span class="term-badge">{t}</span>' for t in terms) + "</div>",
            unsafe_allow_html=True,
        )
    section_card_close()

    # ---- Analogy -----------------------------------------------------------
    section_card_open("03", "Analogy", "quote", extra_class="quote-card")
    st.markdown(f'<div class="quote-mark">{icon("quote")}</div>', unsafe_allow_html=True)
    st.markdown('<div class="prose">', unsafe_allow_html=True)
    st.markdown(result.get("analogy", "") or "_No content returned._")
    st.markdown("</div>", unsafe_allow_html=True)
    section_card_close()

    # ---- Technical explanation ---------------------------------------------
    section_card_open("04", "Technical Explanation", "cpu")
    st.markdown('<div class="prose">', unsafe_allow_html=True)
    st.markdown(result.get("technical_explanation", "") or "_No content returned._")
    st.markdown("</div>", unsafe_allow_html=True)
    section_card_close()

    # ---- Code example --------------------------------------------------
    section_card_open("05", "Code Example", "terminal")
    code_field = result.get("code_example", "") or ""
    code_only, remainder_md = extract_python_code(code_field)
    if code_only:
        st.markdown('<div class="code-label-row"><span class="code-lang-pill">Python</span></div>', unsafe_allow_html=True)
        st.code(code_only, language="python")
        if remainder_md.strip():
            with st.expander("Explanation & usage notes"):
                st.markdown(remainder_md)
    else:
        st.markdown('<div class="prose">', unsafe_allow_html=True)
        st.markdown(code_field or "_No content returned._")
        st.markdown("</div>", unsafe_allow_html=True)
    section_card_close()

    # ---- Quiz ------------------------------------------------------------
    section_card_open("06", "Quiz", "help")
    quiz_body, embedded_answer_key = strip_embedded_answer_key(result.get("quiz", "") or "")
    answers_field = result.get("answers", "") or ""
    correct_letters = parse_answer_letters(embedded_answer_key)
    blocks = parse_mcq_blocks(quiz_body)

    if not blocks or all(not b["prose"].strip() for b in blocks):
        st.markdown('<div class="prose">', unsafe_allow_html=True)
        st.markdown(quiz_body or "_No content returned._")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        answers_split = re.split(r"(?im)^#{1,4}\s*question\s+\d+.*$", answers_field)
        for i, block in enumerate(blocks, start=1):
            st.markdown(f'<div class="quiz-card"><div class="quiz-tag">Question {str(i).zfill(2)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="quiz-question">{block["prose"] if block["prose"] else "See details below."}</div>', unsafe_allow_html=True)

            if block["options"]:
                option_labels = [f"{letter}. {text.strip()}" for letter, text in block["options"]]
                sel_key = f"quiz_sel_{i}"
                selection = st.radio(
                    "Choose an answer",
                    option_labels,
                    key=sel_key,
                    label_visibility="collapsed",
                    index=None,
                )
                submit_col, _ = st.columns([1, 3])
                with submit_col:
                    submitted = st.button("Submit answer", key=f"quiz_submit_{i}")

                if submitted:
                    st.session_state["quiz_submitted"][i] = selection

                chosen = st.session_state["quiz_submitted"].get(i)
                if chosen:
                    chosen_letter = chosen.split(".", 1)[0].strip().upper()
                    correct_letter = correct_letters.get(i)
                    if correct_letter:
                        if chosen_letter == correct_letter:
                            st.markdown(f'<div class="result-pill correct">{icon("check")} Correct</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f'<div class="result-pill incorrect">Incorrect — correct answer is {correct_letter}</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.markdown('<div class="result-pill neutral">Submitted — see explanation below</div>', unsafe_allow_html=True)

            with st.expander("Show answer"):
                if i < len(answers_split):
                    st.markdown(answers_split[i])
                else:
                    st.markdown(answers_field or "_No answer key returned._")

            st.markdown("</div>", unsafe_allow_html=True)
    section_card_close()

    # ---- Revision notes -----------------------------------------------
    section_card_open("07", "Quick Revision", "revision")
    revision_text = result.get("revision_notes", "") or ""
    revision_items = parse_revision_items(revision_text)
    if revision_items:
        st.markdown(
            '<div class="revision-grid">'
            + "".join(
                f'<div class="revision-item"><div class="rterm">{t}</div><div class="rdef">&rarr; {d}</div></div>'
                for t, d in revision_items
            )
            + "</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Full revision notes"):
            st.markdown(revision_text)
    else:
        st.markdown('<div class="prose">', unsafe_allow_html=True)
        st.markdown(revision_text or "_No content returned._")
        st.markdown("</div>", unsafe_allow_html=True)
    section_card_close()

    # ---- Final CTA -----------------------------------------------------
    st.markdown('<div class="final-cta"><h4>Ready to learn something else?</h4>', unsafe_allow_html=True)
    st.markdown('<div class="final-cta-btn">', unsafe_allow_html=True)
    if st.button("Generate Another Module", key="reset_btn"):
        st.session_state["result"] = None
        st.session_state["topic_used"] = ""
        st.session_state["quiz_selections"] = {}
        st.session_state["quiz_submitted"] = {}
        st.rerun()
    st.markdown("</div></div>", unsafe_allow_html=True)