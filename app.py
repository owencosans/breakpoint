"""
BREAKPOINT — application entry point.
War-room simulator: how far channel investment can fall before retailers walk,
competitors enter, and controlled decline becomes collapse.

Run:  streamlit run app.py
"""

import sys
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent
for sub in ("components", "styles", "model", "pages"):
    p = str(_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import ui  # noqa: E402

st.set_page_config(
    page_title="Breakpoint",
    page_icon=str(_ROOT / "assets" / "breakpoint-favicon-64.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.load_theme()

# Control-rail navigation over the six views (spec section 8).
pages = [
    st.Page("pages/01_decision.py", title="Decision", default=True),
    st.Page("pages/02_retailers.py", title="Retailers"),
    st.Page("pages/03_competition.py", title="Competition"),
    st.Page("pages/04_cascade.py", title="Cascade"),
    st.Page("pages/05_assumptions.py", title="Assumptions"),
    st.Page("pages/06_briefing.py", title="Briefing"),
]
nav = st.navigation(pages, position="sidebar")
nav.run()
