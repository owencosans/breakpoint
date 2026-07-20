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

        # A scenario IS its slider posture (presets.py sets nothing else), and
        # keyed sliders keep their session value across reruns — so the presets
        # must be loaded through session state, or picking a scenario changes
        # the blurb and nothing else. The sliders therefore take no value= arg:
        # session state is the single source of their position.
        spec = pr.SCENARIOS[scenario]
        wc_preset = -1.0 if spec["war_chest"] is None else float(spec["war_chest"])
        if st.session_state.get("bp_loaded_scenario") != scenario:
            st.session_state["bp_loaded_scenario"] = scenario
            st.session_state["bp_divest"] = float(spec["divest_pct"])
            st.session_state["bp_wc"] = wc_preset
            st.session_state["bp_alpha"] = float(spec["granite_target_alpha"])

        st.markdown("---")
        ui.eyebrow("Decision controls")
        divest = st.slider("Proposed investment reduction", 0.0, 0.8,
                           step=0.05, key="bp_divest",
                           help="How much discretionary channel investment to cut.")
        war_chest = st.slider("Rival funding (index $/mo)", -1.0, 600.0,
                              step=20.0, key="bp_wc",
                              help="-1 = baseline (no surge). Raise to model an entrant bringing money.")
        alpha = st.slider("Tolerated walkaway risk (per dealer, per month)", 0.01, 0.15,
                          step=0.01, key="bp_alpha",
                          help="Payments are set to hold each dealer's monthly defection "
                               "probability at this level. It is a monthly hazard, not a "
                               "horizon risk — 5%/month compounds to near-certain defection "
                               "over 60 months, which is why the headline Cutline and "
                               "Breakpoint come from the deterministic run.")
        # Ceiling stays at 60: that is the horizon the engine is calibrated and
        # tested at (every test in test_engine.py runs at <=60 months). Beyond
        # it the s4 inflow tap — which compounds at 15%/yr with no saturation —
        # grows the category several times over, inverting the declining-format
        # premise the whole model rests on. Long runs are not evidence here.
        months = st.slider("Horizon (months)", 24, 60, 60, 12, key="bp_months",
                           help="How far ahead cash is accumulated. Capped at 60 months: "
                                "that is the range the model is calibrated and tested at.")

        st.markdown("---")
        st.caption("Stylized market. No client or employer data. Programs modeled "
                   "on proportionally equal terms. Figures are illustrative index units.")

    return {"scenario": scenario, "divest": divest, "war_chest": war_chest,
            "alpha": alpha, "months": months}
