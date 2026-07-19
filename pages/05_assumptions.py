"""BREAKPOINT — Assumptions. Grouped by business meaning, plain-English, with
rationale. Never a wall of unlabeled parameters (spec section 9.6)."""

import sys
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for sub in ("components", "styles", "model"):
    p = str(_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import ui                          # noqa: E402
from sidebar import control_rail   # noqa: E402
import engine as eng               # noqa: E402

ui.load_theme()
P = control_rail()
ui.brand_header()

ui.eyebrow("Assumptions")
st.markdown("#### What the model believes, grouped by business meaning")
st.caption("These are the inputs behind every number in Breakpoint. Each is a stylized figure "
           "calibrated from public benchmarks, not client data. Adjust in code (model/engine.py) "
           "to test alternatives; shown here read-only for transparency in the room.")

p = eng.Params()

GROUPS = {
    "Demand response": [
        ("How much category demand moves on price", "Low (inelastic)",
         "Meta-analytic category elasticity ≈ −0.4; volume barely responds to price."),
        ("How fast customers migrate past the knee", f"{p.beta[1]:.1f} per $",
         "Migration is flat below a threshold, then steep — the S-curve."),
        ("One-way-door penalty on winback", f"{p.kappa:.1f}×",
         "Recapturing a migrated customer costs a multiple of retaining them."),
    ],
    "Retailer economics": [
        ("Margin kept under contract", f"{p.contract_margin_cap*100:.0f}%",
         "Contract caps the dealer's margin on our brands; our payment compensates."),
        ("Selling capacity per retailer (slots)", ", ".join(f"{s:.0f}" for s in p.slots_c),
         "Floor space + rep-hours; the scarce resource retailers allocate."),
        ("Legacy-format share of that capacity", ", ".join(f"{f*100:.0f}%" for f in p.legacy_slot_frac_c),
         "How much of each retailer's shelf is hostage to the declining format."),
        ("Space they'd re-slot if they left", f"{p.k_realloc*100:.0f}%",
         "Off contract, capacity a dealer converts to the growth format."),
    ],
    "Channel access": [
        ("Our visibility floor under contract", f"{p.v_floor*100:.0f}%",
         "Guaranteed shelf presence while the contract holds."),
        ("Rival spend allowed under contract", f"{p.rival_modern_bid_cap*100:.0f}%",
         "How much rival money the store can take while on our contract."),
        ("Shelf-turns-against-us on defection", f"{p.contract_loss_hazard_mult:.1f}×",
         "Losing a retailer accelerates our customer loss there — the shelf now promotes rivals."),
    ],
    "Rival funding": [
        ("Baseline rival spend rate", f"{p.nordkapp_base_rate:.0f}",
         "The entrant's peacetime investment before any surge."),
        ("Rival reinvestment as it grows", f"{p.nordkapp_reinvest_annual*100:.0f}%/yr",
         "The leader compounds its spend as the growth category expands."),
    ],
    "Retention & recovery": [
        ("Switching cost buffer", ", ".join(f"{(p.stickiness_factor*p.W_c0)[i]:.1f}" for i in range(3)),
         "Disruption cost that keeps a retailer in place near indifference."),
        ("Cost premium to reverse a defection", f"{p.reversal_premium*100:.0f}%",
         "Winning a retailer back costs more than it took to keep them."),
    ],
    "Our posture": [
        ("Defense budget ceiling", f"{p.granite_defense_budget_mult:.2f}× base spend",
         "We cannot out-pay a surge everywhere at once; we ration toward what matters."),
        ("Tolerated walkaway risk", f"{P['alpha']*100:.0f}%",
         "How much defection probability we accept when setting payments."),
    ],
}

for group, rows in GROUPS.items():
    ui.eyebrow(group)
    for label, value, rationale in rows:
        st.markdown(
            f'<div class="bp-card"><div style="display:flex;justify-content:space-between">'
            f'<span>{label}</span>'
            f'<span class="bp-card-value" style="font-size:1.0rem">{value}</span></div>'
            f'<div class="bp-card-sub">{rationale}</div></div>',
            unsafe_allow_html=True)
    st.markdown("")
