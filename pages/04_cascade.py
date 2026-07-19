"""BREAKPOINT — Cascade. Order of vulnerability and how one defection changes
the next retailer's economics."""

import sys
from pathlib import Path
import numpy as np
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for sub in ("components", "styles", "model"):
    p = str(_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import ui, charts, decision as dec  # noqa: E402
from sidebar import control_rail    # noqa: E402

ui.load_theme()
P = control_rail()
ui.brand_header()

ui.eyebrow("Cascade")
st.markdown("#### One retailer leaving changes the economics of the next")

board = dec.retailer_board(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])
R = dec.run_scenario(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])

st.plotly_chart(charts.cascade_blocks(board, R["first_defection"]), width="stretch")

# ordered explanation of propagation
st.markdown("##### Order of vulnerability")
for i, r in enumerate(board, 1):
    col = {"HELD": ui.C["teal"], "PRESSURE": ui.C["amber"],
           "WALKAWAY RISK": ui.C["amber"], "BREAKPOINT": ui.C["red"]}[r["state"]]
    st.markdown(
        f'<div class="bp-card" style="border-left:3px solid {col}">'
        f'<b>{i}. {r["label"]}</b> &nbsp; {ui.badge(r["state"])}<br>'
        f'<span class="bp-card-sub">Buffer {r["distance"]:+.2f}× switching cost · '
        f'a rival offer near {r["rival_offer_required"]:.1f} would tip it</span></div>',
        unsafe_allow_html=True)

any_defect = any(r["defected"] for r in board)
if any_defect:
    ui.warning("Cascade begins",
               "When the first retailer leaves, its shelf turns to promoting rivals, the growth "
               "format's visibility rises, category decline steepens, and the next retailer's "
               "leave-vs-stay math improves — pulling the following defection closer.")
else:
    st.markdown(
        f'<div class="bp-card" style="border-left:3px solid {ui.C["teal"]}">'
        f'No defection on the current settings. The chain is intact — but note the ordering: '
        f'{board[0]["retailer"]} is the first domino, and it is the one to watch.</div>',
        unsafe_allow_html=True)

st.caption("Ordering is by how close each retailer sits to its walkaway point. The first to flip "
           "is not always the biggest — it's the one whose floor space is most hostage to the "
           "declining format.")
