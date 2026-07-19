"""BREAKPOINT — Retailers. Walkaway table + stay-vs-leave economics."""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
for sub in ("components", "styles", "model"):
    p = str(_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import ui, charts, decision as dec  # noqa: E402
from sidebar import control_rail    # noqa: E402
import retailer as ret              # noqa: E402
import engine as eng                # noqa: E402

ui.load_theme()
P = control_rail()
ui.brand_header()

ui.eyebrow("Retailers")
st.markdown("#### Sit on Hartline's side of the desk")
st.caption("Every dealer runs the same monthly math: what staying pays versus what leaving pays. "
           "Our check only has to beat the difference.")

board = dec.retailer_board(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])

st.markdown(
    f'<div class="bp-card" style="border-left:3px solid {ui.C["amber"]}">'
    'The contract caps the dealer\'s margin on our plans <b>and</b> caps how much rival money '
    'the store is allowed to take. The payment compensates for both — which is why its ROI '
    'was never the point.</div>',
    unsafe_allow_html=True)

# ---- walkaway table ----
def fmt_state(s):
    return s
tbl = pd.DataFrame([{
    "Retailer": r["label"],
    "Stays (all-in)": f"{r['stay']:.1f}",
    "Leaves (net)": f"{r['defect']:.1f}",
    "Walkaway pay": f"{r['walkaway_pay']:.1f}",
    "Breaks at cut": (f"{r['breaks_at']*100:.0f}%" if r["breaks_at"] is not None else "holds"),
    "Rival $ to tip": f"{r['rival_offer_required']:.1f}",
    "State": r["state"],
} for r in board])
st.dataframe(tbl, width="stretch", hide_index=True)

# state badges row
cols = st.columns(len(board))
for r, c in zip(board, cols):
    with c:
        st.markdown(ui.badge(r["state"]), unsafe_allow_html=True)
        st.caption(r["label"])

st.markdown("---")

# ---- stay-vs-leave for a chosen retailer ----
names = {r["retailer"]: r["label"] for r in board}
pick = st.radio("Retailer", list(names.keys()), horizontal=True,
                format_func=lambda k: names[k], label_visibility="collapsed")

R = dec.run_scenario(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])
p = eng.Params(months=P["months"], granite_target_alpha=P["alpha"])
hist_like = {"t": list(range(R["months"])), "pop": R["pop"],
             "trade_bid": R["trade_bid"], "granite_pay": R["granite_pay"]}
pnl = ret.pnl_timeseries(hist_like, p)
D = pnl[pick]
mo = st.slider("Month", 0, R["months"] - 1, R["months"] - 1, 1)

c1, c2 = st.columns([3, 2])
with c1:
    st.plotly_chart(
        charts.stay_vs_leave(D["stay_components"][mo], D["defect_components"][mo],
                             D["switching_cost"], names[pick]),
        width="stretch")
with c2:
    prem = D["defection_premium"][mo]
    ui.card("Stays (all-in)", f"{D['stay_total'][mo]:.1f}", "$ / month")
    ui.card("Leaves (net of switch cost)", f"{D['defect_total'][mo]-D['switching_cost']:.1f}", "$ / month")
    ui.card("Net leave premium", f"{prem:+.1f}",
            "positive = leaving is rational", ui.C["red"] if prem > 0 else ui.C["teal"])
    ets = D["economic_T_star"]
    ui.card("When leaving pencils", f"mo {ets}" if ets is not None else "not on this policy",
            "first month the math flips", ui.C["red"] if ets is not None else ui.C["teal"])

st.caption("Read the two stacks against each other. Leaving unlocks open margins, every rival's "
           "checks, and the option to re-slot shelf space to the growth format — minus the cost "
           "of switching. When the growth format out-earns the legacy shelf, that math flips on "
           "its own. That drift is what the payment is fighting, and it is why cutting the "
           "payment and cutting the risk are not the same move.")
