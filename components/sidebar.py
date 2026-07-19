"""BREAKPOINT shared control rail (sidebar). Returns the active parameter set
so every page reads the same controls (spec section 14)."""

from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st

_MODEL = Path(__file__).resolve().parent.parent / "model"
if str(_MODEL) not in sys.path:
    sys.path.insert(0, str(_MODEL))
import presets as pr  # noqa: E402

import ui  # noqa: E402  (same components dir)


def control_rail():
    with st.sidebar:
        ui.sidebar_brand()
        ui.eyebrow("Scenario")
        scenario = st.selectbox("Scenario", list(pr.SCENARIOS.keys()),
                                label_visibility="collapsed", key="bp_scenario")
        st.caption(pr.SCENARIOS[scenario]["blurb"])

        st.markdown("---")
        ui.eyebrow("Decision controls")
        spec = pr.SCENARIOS[scenario]
        divest = st.slider("Proposed investment reduction", 0.0, 0.8,
                           float(spec["divest_pct"]), 0.05, key="bp_divest",
                           help="How much discretionary channel investment to cut.")
        wc_default = -1.0 if spec["war_chest"] is None else spec["war_chest"]
        war_chest = st.slider("Rival funding (index $/mo)", -1.0, 600.0,
                              float(wc_default), 20.0, key="bp_wc",
                              help="-1 = baseline (no surge). Raise to model an entrant bringing money.")
        alpha = st.slider("Tolerated walkaway risk", 0.01, 0.15,
                          float(spec["granite_target_alpha"]), 0.01, key="bp_alpha")
        months = st.slider("Horizon (months)", 24, 60, 60, 12, key="bp_months")

        st.markdown("---")
        st.caption("Stylized market. No client or employer data. Programs modeled "
                   "on proportionally equal terms. Figures are illustrative index units.")

    return {"scenario": scenario, "divest": divest, "war_chest": war_chest,
            "alpha": alpha, "months": months}
