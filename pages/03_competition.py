"""BREAKPOINT — Competition. Entry Pressure (B*) and the tipping phase field."""

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
import presets as pr                # noqa: E402
import engine as eng                # noqa: E402

ui.load_theme()
P = control_rail()
ui.brand_header()

ui.eyebrow("Competition")
st.markdown("#### NORD's money doesn't fight for customers first — it bids for the shelf")
st.caption("Entry Pressure is the funding level where rival offers flip at least two dealers. "
           "Below it the network holds; above it, defections cascade.")

res = st.select_slider("Resolution", options=[8, 12, 16], value=12,
                       help="Higher = smoother phase field, slower first compute (cached after).")
ph = dec.phase_field(P["alpha"], res, P["months"])
ep = dec.entry_pressure(P["scenario"], P["alpha"], P["months"])
defense = float(np.clip(1.0 - (P["alpha"] - 0.01) / (0.15 - 0.01), 0, 1))
cur_wc = pr.peacetime_war_chest(eng.Params()) if P["war_chest"] < 0 else P["war_chest"]

c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(charts.phase_diagram(ph, ep["b_star"], cur_wc, defense), width="stretch")
with c2:
    ui.card("Entry Pressure", f"{ep['b_star']:.0f}" if ep["ignites"] else f">{ep['b_star']:.0f}",
            "rival $/mo that tips ≥2 retailers", ui.C["red"] if ep["ignites"] else ui.C["teal"])
    R = dec.run_scenario(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])
    fd = R["first_defection"]
    ui.card("This scenario", f"defect mo {fd}" if fd is not None else "holds",
            "first retailer defection", ui.C["red"] if fd is not None else ui.C["teal"])
    st.markdown(
        "Raise **Rival funding** in the control rail past Entry Pressure and watch the first "
        "defection move forward. A rival's money doesn't just fight for customers — it enters "
        "every retailer's leave-vs-stay math at once. One side effect to read correctly: a "
        "surge also *inflates* the savings figure on the Decision page, because costlier "
        "defense leaves more spend to trim — while total cash falls.")

st.caption("Green = stable. Amber = contested. Red = the rival funding level where defections "
           "cascade. The white × is where you are. The distance from it to the red region is how "
           "much rival money the system can absorb before the shelf starts changing hands.")
