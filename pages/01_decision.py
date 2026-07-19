"""BREAKPOINT — Decision (landing). Answers four questions in 15 seconds:
what cut, how much headroom, who's closest to walking, what if we overshoot."""

import sys
from pathlib import Path
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

ui.brand_header("Find the cut that changes everything.")

cut = dec.cutline(P["scenario"], P["war_chest"], P["alpha"], P["months"])
board = dec.retailer_board(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])
state = dec.overall_state(board, cut, P["divest"])
closest = board[0]

ui.eyebrow("Decision")
st.markdown("#### The recommended posture, and the boundary you should not cross")

# ---- hero row: the dominant output ----
h1, h2, h3 = st.columns([2, 2, 2])
with h1:
    ui.hero_card("Recommended cut (Cutline)", f"{cut['cutline_pct']*100:.0f}%",
                 f"captures {ui.money(cut['recoverable'])} of savings")
with h2:
    ui.card("Headroom to Breakpoint", f"{cut['headroom_pct']*100:.0f}%",
            f"Breakpoint at {cut['breakpoint_pct']*100:.0f}% cut", ui.C["amber"])
with h3:
    col = {"HELD": ui.C["teal"], "PRESSURE": ui.C["amber"],
           "WALKAWAY RISK": ui.C["amber"], "BREAKPOINT": ui.C["red"]}[state]
    ui.card("Current posture", state,
            f"at your proposed {P['divest']*100:.0f}% cut", col)

# ---- the decision band ----
st.plotly_chart(charts.decision_band(cut, P["divest"]), width="stretch")

# ---- four-question strip ----
q1, q2, q3, q4 = st.columns(4)
with q1:
    ui.card("What cut is recommended?", f"{cut['cutline_pct']*100:.0f}%", "the Cutline", ui.C["teal"])
with q2:
    ui.card("Savings recovered", ui.money(cut["recoverable"]), "vs. paying full freight", ui.C["green"])
with q3:
    cs_state = closest["state"]
    cs_col = {"HELD": ui.C["teal"], "PRESSURE": ui.C["amber"],
              "WALKAWAY RISK": ui.C["amber"], "BREAKPOINT": ui.C["red"]}[cs_state]
    ui.card("Closest to walking", closest["retailer"],
            f"{closest['distance']:.2f}× switch-cost buffer", cs_col)
with q4:
    ui.card("If you overshoot", f"{cut['breakpoint_pct']*100:.0f}%+",
            "cut here → a retailer walks", ui.C["red"])

# ---- consequence line ----
if state == "BREAKPOINT":
    ui.warning("Breakpoint crossed",
               f"At a {P['divest']*100:.0f}% cut, at least one retailer is now economically "
               f"better off leaving. Recovery costs more than the savings retained. "
               f"Pull back below {cut['breakpoint_pct']*100:.0f}%.")
elif state in ("PRESSURE", "WALKAWAY RISK"):
    st.markdown(
        f'<div class="bp-card" style="border-left:3px solid {ui.C["amber"]}">'
        f'You are past the Cutline ({cut["cutline_pct"]*100:.0f}%) but below the Breakpoint '
        f'({cut["breakpoint_pct"]*100:.0f}%). Additional cuts add risk faster than savings. '
        f'{closest["retailer"]} is closest to its walkaway point.</div>',
        unsafe_allow_html=True)
else:
    st.markdown(
        f'<div class="bp-card" style="border-left:3px solid {ui.C["teal"]}">'
        f'All retailers held. The recommended cut recovers {ui.money(cut["recoverable"])} while '
        f'preserving every current relationship. Room remains before the Breakpoint.</div>',
        unsafe_allow_html=True)

st.caption("Cutline = recommended reduction. Breakpoint = where controlled decline becomes "
           "collapse. The space between is your margin for error.")
