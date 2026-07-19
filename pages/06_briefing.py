"""BREAKPOINT — Briefing. One-page executive export, print-ready."""

import sys
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_ROOT = Path(__file__).resolve().parent.parent
for sub in ("components", "styles", "model"):
    p = str(_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import ui, decision as dec                       # noqa: E402
from sidebar import control_rail                 # noqa: E402
from briefing_export import build_briefing_html  # noqa: E402

ui.load_theme()
P = control_rail()
ui.brand_header()

ui.eyebrow("Briefing")
st.markdown("#### The one-page assessment, ready for the room")

cut = dec.cutline(P["scenario"], P["war_chest"], P["alpha"], P["months"])
board = dec.retailer_board(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])
state = dec.overall_state(board, cut, P["divest"])
entry = dec.entry_pressure(P["scenario"], P["alpha"], P["months"])

html = build_briefing_html(P, cut, board, state, entry, ui.money)

c1, c2 = st.columns([1, 1])
with c1:
    st.download_button("Download briefing (HTML → print to PDF)", data=html,
                       file_name=f"breakpoint_assessment_{P['scenario'].replace(' ', '_').lower()}.html",
                       mime="text/html", width="stretch")
with c2:
    st.caption("Open the file and print to PDF (light background, executive layout). "
               "Or present the live preview below.")

st.markdown("---")
components.html(html, height=1100, scrolling=True)
