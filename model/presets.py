"""
BREAKPOINT model -- Scenario presets (build spec section 5 sidebar).
Each preset returns a (Params, levers_fn) pair so app.py can run it directly.
Presets are thin: they set a few Params fields and choose the default levers_fn
knobs (divest %, entrant war chest). The heterogeneity and mechanics all live
in engine.py -- presets just dial the exogenous conditions.
"""

from __future__ import annotations
from dataclasses import replace
import engine as eng


# Master default knobs, surfaced in the sidebar and overridable live.
SCENARIOS = {
    "Status Quo Harvest": {
        "blurb": "Baseline. Pay to hold every dealer, entrant at peacetime spend. "
                 "The melting-ice-cube world before anyone does anything.",
        "divest_pct": 0.00,
        "war_chest": None,          # None -> engine's growing peacetime NORD rate
        "granite_target_alpha": 0.05,
    },
    "Aggressive Divestment": {
        "blurb": "Cut dealer spend hard to recover promo ROI. Tests how far the "
                 "throttle closes before a participation constraint snaps.",
        "divest_pct": 0.45,
        "war_chest": None,
        "granite_target_alpha": 0.05,
    },
    "NORD Surge": {
        "blurb": "Entrant brings real money to the table, aimed where digital "
                 "volume flows. Watch Nova before Hartline.",
        "divest_pct": 0.00,
        "war_chest": 380.0,
        "granite_target_alpha": 0.05,
    },
    "Fortress": {
        "blurb": "Defend everything at low tolerated defection risk, even under "
                 "an entrant surge. Expensive insurance -- is it worth it?",
        "divest_pct": 0.00,
        "war_chest": 380.0,
        "granite_target_alpha": 0.02,
    },
}


def build(scenario_name: str,
          divest_pct: float | None = None,
          war_chest: float | None = None,
          alpha: float | None = None,
          months: int = 60):
    """
    Resolve a scenario (plus any live sidebar overrides) into (Params, levers_fn).
    Passing an explicit arg overrides the preset default; None falls back to it.
    war_chest is special: the sentinel -1.0 from a slider means "peacetime"
    (engine default), since Streamlit sliders can't hold Python None.
    """
    spec = SCENARIOS[scenario_name]

    d = spec["divest_pct"] if divest_pct is None else divest_pct
    a = spec["granite_target_alpha"] if alpha is None else alpha

    if war_chest is None:
        wc = spec["war_chest"]
    elif war_chest < 0:
        wc = None
    else:
        wc = war_chest

    p = eng.Params(months=months, granite_target_alpha=a)
    levers_fn = eng.default_levers_fn(divest_pct=d, war_chest_override=wc)
    return p, levers_fn


def peacetime_war_chest(p: eng.Params, t: int = 0) -> float:
    """The NORD spend rate the engine uses at t when war_chest_override is None
    -- handy for labeling the 'peacetime' end of the invasion sweep axis."""
    return p.nordkapp_base_rate * (1.0 + p.nordkapp_reinvest_annual) ** (t / 12.0)
