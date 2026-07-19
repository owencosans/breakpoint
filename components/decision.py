"""
BREAKPOINT model adapter.

One place that runs the simulation and translates raw engine output into the
product's plain-English decision language (spec section 3): Cutline, Walkaway
Point, Entry Pressure, and the four states HELD / PRESSURE / WALKAWAY RISK /
BREAKPOINT. Every page imports from here so the vocabulary is consistent and
the sim runs once per parameter set (Streamlit-cached).

Money framing: the engine works in abstract index units. For an executive
audience we surface a $MM scale via MONEY_SCALE (a presentation multiplier
only — clearly a stylized figure, not a claim about real dollars).
"""

from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import streamlit as st

_MODEL = Path(__file__).resolve().parent.parent / "model"
if str(_MODEL) not in sys.path:
    sys.path.insert(0, str(_MODEL))

import engine as eng          # noqa: E402
import analysis as an         # noqa: E402
import presets as pr          # noqa: E402
import retailer as ret        # noqa: E402

MONEY_SCALE = 1.0  # index units are already on a $MM-like scale for the demo

RETAILERS = ["HARTLINE", "NOVA", "INDIES"]
# "INDIES" stays as the engine's internal key; the display name avoids the
# trade term "independents" — plain-English labels only, per the owner.
RETAILER_LABEL = {
    "HARTLINE": "Hartline (legacy-heavy)",
    "NOVA": "Nova (growth-heavy)",
    "INDIES": "Crosstown Mobile (price-led)",
}

# Bare names, for copy that reads as a sentence rather than a table cell.
RETAILER_SHORT = {
    "HARTLINE": "Hartline",
    "NOVA": "Nova",
    "INDIES": "Crosstown",
}

# Why each one is exposed — the mechanism, not the ranking (Cascade view).
RETAILER_MECHANISM = {
    "HARTLINE": "roughly three-quarters of its book is contract-plan commission — its "
                "shelf is hostage to the melting format",
    "NOVA": "mostly digital activations, so every rival offer lands where the volume "
            "actually flows and gets a meeting",
    "INDIES": "competes on price with the lowest switching costs on the board — "
              "first to flip",
}


# ----------------------------------------------------------------------------
# Core cached run + derived decision quantities
# ----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def run_scenario(scenario: str, divest: float, war_chest: float, alpha: float,
                 months: int, seed=None):
    p, lf = pr.build(scenario, divest_pct=divest, war_chest=war_chest, alpha=alpha, months=months)
    hist = eng.run(p, levers_fn=lf, months=months, seed=seed)
    return {
        "legacy": eng.legacy_total(hist), "modern": eng.modern_total(hist),
        "brands": {b: eng.brand_total(hist, eng.BI[b]) for b in
                   ["GRANITE_SELECT", "BOWERS", "GRANITE_ONE", "BOWER_FRESH", "NORD"]},
        "D": hist["D"], "O_c": hist["O_c"], "granite_pay": hist["granite_pay"],
        "contract_held": hist["contract_held"], "pop": hist["pop"],
        "trade_bid": hist["trade_bid"],
        "npv": hist["final_state"].cash["GRANITE"],
        "first_defection": eng.first_defection_month(hist),
        "months": months,
    }


@st.cache_data(show_spinner=True)
def cutline(scenario: str, war_chest: float, alpha: float, months: int):
    """
    Two decision boundaries an executive can trust:

    - BREAKPOINT: the first cut depth at which the *deterministic* run starts
      losing contracts. This is the structural cliff -- no stochastic noise,
      just "cut this far and a retailer walks on the central case."
    - CUTLINE: the recommended cut. The largest reduction that (a) stays below
      the Breakpoint and (b) captures the great majority of the achievable NPV
      gain -- i.e. where the curve has plateaued and further cutting only adds
      risk. Defined as the knee: smallest cut capturing >=90% of the max NPV
      improvement, capped one grid-step below the Breakpoint.
    """
    grid = np.linspace(0, 0.8, 33)
    wc = None if war_chest < 0 else war_chest

    npv = np.zeros(len(grid))
    det_defect_depth = None  # first cut where deterministic run loses a contract
    for i, d in enumerate(grid):
        p = eng.Params(months=months, granite_target_alpha=alpha)
        lf = eng.default_levers_fn(divest_pct=float(d), war_chest_override=wc)
        hist = eng.run(p, levers_fn=lf, months=months, seed=None)  # deterministic
        npv[i] = hist["final_state"].cash["GRANITE"]
        if det_defect_depth is None and eng.first_defection_month(hist) is not None:
            det_defect_depth = float(d)

    breakpoint_pct = det_defect_depth if det_defect_depth is not None else float(grid[-1])
    breakpoint_idx = int(np.argmin(np.abs(grid - breakpoint_pct)))

    # NPV capture knee, restricted to the pre-breakpoint region
    safe_region = grid < breakpoint_pct
    if safe_region.any():
        npv_safe = npv.copy()
        npv_safe[~safe_region] = -np.inf
        base, peak_val = npv[0], np.max(npv_safe)
        target = base + 0.90 * (peak_val - base) if peak_val > base else peak_val
        knee_candidates = np.where((npv >= target) & safe_region)[0]
        cutline_idx = int(knee_candidates[0]) if len(knee_candidates) else 0
    else:
        cutline_idx = 0
    cutline_pct = float(grid[cutline_idx])

    return {
        "grid": grid, "npv": npv,
        "cutline_pct": cutline_pct, "cutline_idx": cutline_idx,
        "breakpoint_pct": breakpoint_pct, "breakpoint_idx": breakpoint_idx,
        "npv_at_cutline": float(npv[cutline_idx]),
        "npv_at_zero": float(npv[0]),
        "recoverable": float(npv[cutline_idx] - npv[0]),
        "headroom_pct": max(0.0, breakpoint_pct - cutline_pct),
    }


def retailer_state(distance_frac: float, defected: bool) -> str:
    """Map a retailer's distance-to-walkaway (safety buffer as a multiple of the
    switching cost) into one of the four states."""
    if defected:
        return "BREAKPOINT"
    if distance_frac <= 0.0:
        return "WALKAWAY RISK"
    if distance_frac < 0.75:
        return "PRESSURE"
    return "HELD"


@st.cache_data(show_spinner=False)
def retailer_board(scenario: str, divest: float, war_chest: float, alpha: float, months: int):
    """
    Per-retailer decision economics at the horizon: current vs post-cut
    economics, walkaway point, distance to walkaway, rival offer required,
    and state. Uses the structural dealer P&L (retailer.py).
    """
    R = run_scenario(scenario, divest, war_chest, alpha, months)
    p = eng.Params(months=months, granite_target_alpha=alpha)
    hist_like = {"t": list(range(R["months"])), "pop": R["pop"],
                 "trade_bid": R["trade_bid"], "granite_pay": R["granite_pay"]}
    pnl = ret.pnl_timeseries(hist_like, p)

    rows = []
    t = R["months"] - 1
    for c in RETAILERS:
        ci = eng.CI[c]
        d = pnl[c]
        stay = d["stay_total"][t]
        defect = d["defect_total"][t] - d["switching_cost"]
        premium = d["defection_premium"][t]           # defect - switchcost - stay
        walkaway_pay = R["O_c"][t, ci]                # payment level at which O == W
        current_pay = R["granite_pay"][t, ci]
        # Distance to walkaway: the safety buffer as a fraction of the switching
        # cost that stands between the retailer and indifference. premium<0 means
        # staying wins; the closer premium is to 0 (relative to switch cost), the
        # closer to flipping. Entrant money that lifts the defect side shrinks
        # this correctly.
        switch = max(d["switching_cost"], 1e-6)
        distance = (-premium) / switch
        defected = not R["contract_held"][t, ci]
        rows.append({
            "retailer": c, "label": RETAILER_LABEL[c],
            "stay": stay, "defect": defect, "premium": premium,
            "walkaway_pay": walkaway_pay, "current_pay": current_pay,
            "distance": distance, "defected": defected,
            "economic_T_star": d["economic_T_star"],
            "state": retailer_state(distance, defected),
            "rival_offer_required": max(0.0, walkaway_pay),
        })
    # closest to walkaway first
    rows.sort(key=lambda r: (not r["defected"], r["distance"]))
    return rows


@st.cache_data(show_spinner=False)
def spend_jobs(scenario: str, war_chest: float, alpha: float, months: int):
    """The four jobs the channel investment is doing (analysis.four_jobs).

    Read-only use of the model layer. Demo-grade decomposition — every surface
    that renders this must keep the word "illustrative" in the caption.
    """
    wc = None if war_chest < 0 else war_chest
    p = eng.Params(months=months, granite_target_alpha=alpha)
    return an.four_jobs(p, wc, alpha, months=months, seed=None)


@st.cache_data(show_spinner=True)
def entry_pressure(scenario: str, alpha: float, months: int):
    """Entry Pressure: the rival funding level (B*) that tips >=2 retailers,
    plus the phase field for the Competition view."""
    defense = 1.0 - (alpha - 0.01) / (0.15 - 0.01)
    bstar, ignites = an.find_b_star(alpha, defense=float(np.clip(defense, 0, 1)), seeds=(1, 2, 3, 4, 5))
    return {"b_star": float(bstar), "ignites": bool(ignites)}


@st.cache_data(show_spinner=True)
def phase_field(alpha: float, res: int, months: int):
    eg = np.linspace(60, 600, res)
    ig = np.linspace(0.0, 1.0, max(res - 3, 6))
    return an.invasion_phase_grid(alpha, incumbent_grid=ig, entrant_grid=eg, seeds=(1, 2), months=months)


def overall_state(board, cut_info, proposed_divest):
    """The single headline state for the Decision screen."""
    if any(r["defected"] for r in board):
        return "BREAKPOINT"
    if proposed_divest >= cut_info["breakpoint_pct"]:
        return "BREAKPOINT"
    if any(r["state"] == "WALKAWAY RISK" for r in board):
        return "WALKAWAY RISK"
    if proposed_divest > cut_info["cutline_pct"] or any(r["state"] == "PRESSURE" for r in board):
        return "PRESSURE"
    return "HELD"
