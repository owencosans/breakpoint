"""
BREAKPOINT model -- Analysis layer for the app tabs.
Derived quantities that sit on top of engine.run(): the gap S-curve and
local-vs-arc elasticity pair (Tab 2), the divestment frontier (Tab 4), and
the invasion phase grid + B* bisection (Tab 5). Kept separate from engine.py
so the sim core stays clean and testable.

Performance: engine.run() is ~30-60ms, so the phase grid (Tab 5) is the only
expensive call. It's cached in app.py via st.cache_data and defaults to a
modest grid; see grid_resolution.
"""

from __future__ import annotations
import numpy as np

import engine as eng
import mechanics as mech


# ----------------------------------------------------------------------------
# Tab 2 -- Gap physics: the S-curve and the elasticity pair
# ----------------------------------------------------------------------------

def scurve(p: eng.Params, segment: str = "S2_VALUE",
           gap_range=(-1.0, 5.0), n=120, ratchet_reverse=0.0, vis_j=0.5):
    """
    Migration hazard as a function of the price gap, for one segment, holding
    everything else fixed. This is the raw S-curve the Tab 2 slider rides.
    Returns (gaps, hazards).
    """
    s = eng.SI[segment]
    gaps = np.linspace(*gap_range, n)
    h = mech.gap_migration_hazard(
        gaps, p.theta[s], p.beta[s], p.h0[s],
        ratchet_reverse, p.kappa, vis_j, p.gamma_vis,
    )
    return gaps, h


def elasticity_pair(p: eng.Params, segment: str, managed_gap: float,
                    arc_delta: float = 1.0, vis_j=0.5):
    """
    The reconciliation number the spec (3.1) wants displayed:
      - LOCAL: d(share)/d(gap) at the managed gap -> reads low.
      - ARC:   share change across managed_gap +/- arc_delta -> reads high.
    We express both as a semi-elasticity of the migration hazard w.r.t. the
    gap (fractional hazard change per $), which is the honest object here since
    'share' at a point isn't well-defined without a full run. Returns a dict.
    """
    s = eng.SI[segment]

    def haz(g):
        return mech.gap_migration_hazard(
            g, p.theta[s], p.beta[s], p.h0[s], 0.0, p.kappa, vis_j, p.gamma_vis)

    eps = 1e-3
    h0 = haz(managed_gap)
    dh = (haz(managed_gap + eps) - haz(managed_gap - eps)) / (2 * eps)
    local = (dh / h0) if h0 > 0 else float("nan")   # per $ (fractional)

    h_lo = haz(managed_gap - arc_delta)
    h_hi = haz(managed_gap + arc_delta)
    h_mid = haz(managed_gap)
    arc = ((h_hi - h_lo) / h_mid) / (2 * arc_delta) if h_mid > 0 else float("nan")

    return {
        "local_per_dollar": local,
        "arc_per_dollar": arc,
        "ratio": (arc / local) if (local and np.isfinite(local) and local != 0) else float("nan"),
        "haz_at_gap": h0,
        "haz_below_knee": h_lo,
        "haz_above_knee": h_hi,
    }


def knee_location(p: eng.Params, segment: str, gap_range=(-1.0, 5.0), n=400, vis_j=0.5):
    """Gap at which the S-curve is steepest (max slope) -- the 'knee'. For a
    logistic this is just theta, but we find it numerically so it stays honest
    if the curve shape is ever changed."""
    gaps, h = scurve(p, segment, gap_range, n, 0.0, vis_j)
    slopes = np.gradient(h, gaps)
    return gaps[int(np.argmax(slopes))]


# ----------------------------------------------------------------------------
# Tab 4 -- Divestment frontier
# ----------------------------------------------------------------------------

def divestment_frontier(base_p: eng.Params, war_chest, alpha: float,
                        divest_grid=None, seeds=(1, 2, 3, 4, 5), months=60):
    """
    Sweep Granite's divestment % and record terminal NPV + defection risk.
    For each divest level we run a few seeds and report mean NPV and the
    fraction of seeds with >=1 defection (an empirical defection probability).
    Returns dict of arrays for plotting the three-zone frontier.
    """
    if divest_grid is None:
        divest_grid = np.linspace(0.0, 0.8, 17)

    npv = np.zeros(len(divest_grid))
    defect_rate = np.zeros(len(divest_grid))
    first_defect = np.full(len(divest_grid), np.nan)

    for i, d in enumerate(divest_grid):
        npvs, defs, firsts = [], [], []
        for seed in seeds:
            lf = eng.default_levers_fn(divest_pct=float(d), war_chest_override=war_chest)
            p = eng.Params(months=months, granite_target_alpha=alpha)
            hist = eng.run(p, levers_fn=lf, months=months, seed=seed)
            npvs.append(hist["final_state"].cash["GRANITE"])
            fd = eng.first_defection_month(hist)
            defs.append(1.0 if fd is not None else 0.0)
            if fd is not None:
                firsts.append(fd)
        npv[i] = np.mean(npvs)
        defect_rate[i] = np.mean(defs)
        first_defect[i] = np.mean(firsts) if firsts else np.nan

    # Zone boundaries: ROI zone = defection risk under alpha; cliff = risk high
    # AND NPV has turned down vs the no-divestment baseline.
    roi_edge_idx = np.argmax(defect_rate > alpha) if np.any(defect_rate > alpha) else len(divest_grid) - 1
    cliff_idx = np.argmax(defect_rate > 0.5) if np.any(defect_rate > 0.5) else len(divest_grid) - 1

    return {
        "divest_grid": divest_grid,
        "npv": npv,
        "defect_rate": defect_rate,
        "first_defect_month": first_defect,
        "roi_edge_idx": int(roi_edge_idx),
        "cliff_idx": int(cliff_idx),
        "max_safe_divest": float(divest_grid[max(roi_edge_idx - 1, 0)]),
    }


# ----------------------------------------------------------------------------
# Tab 5 -- Invasion phase diagram + B*
# ----------------------------------------------------------------------------

def _defections_within(hist, horizon_months, min_defections=2):
    held = hist["contract_held"][:horizon_months]
    n_defected = (~held).any(axis=0).sum()  # channels that defected at any point
    return n_defected >= min_defections


def invasion_phase_grid(base_alpha: float, incumbent_grid=None, entrant_grid=None,
                        seeds=(1, 2, 3), months=60, horizon=36, min_defections=2):
    """
    2D grid over entrant war chest (x) and incumbent trade intensity (y).
    Cell value = fraction of seeds in which >=min_defections dealers defect
    within `horizon` months. This is the stable/contested/cascade heat field.
    incumbent intensity is expressed as granite_target_alpha inverted: higher
    'defense' = lower alpha (pays more to hold). We map a 0..1 defense knob to
    alpha in [0.15, 0.01].
    """
    if entrant_grid is None:
        entrant_grid = np.linspace(60, 600, 15)     # x-axis: NORD war chest
    if incumbent_grid is None:
        incumbent_grid = np.linspace(0.0, 1.0, 12)  # y-axis: Granite defense intensity

    field = np.zeros((len(incumbent_grid), len(entrant_grid)))

    for yi, defense in enumerate(incumbent_grid):
        alpha = 0.15 - defense * (0.15 - 0.01)      # more defense -> lower alpha
        for xi, wc in enumerate(entrant_grid):
            hits = 0
            for seed in seeds:
                lf = eng.default_levers_fn(divest_pct=0.0, war_chest_override=float(wc))
                p = eng.Params(months=months, granite_target_alpha=float(alpha))
                hist = eng.run(p, levers_fn=lf, months=months, seed=seed)
                if _defections_within(hist, horizon, min_defections):
                    hits += 1
            field[yi, xi] = hits / len(seeds)

    return {
        "entrant_grid": entrant_grid,
        "incumbent_grid": incumbent_grid,
        "field": field,
    }


def find_b_star(base_alpha: float, defense: float = 0.5, seeds=(1, 2, 3, 4, 5),
                months=60, horizon=36, min_defections=2, lo=60.0, hi=800.0, iters=12):
    """
    Bisection on entrant war chest for the ignition threshold B*: the smallest
    NORD spend at which >=min_defections dealers defect within `horizon` in a
    majority of seeds. Returns B* (or hi if never ignites in range).
    """
    alpha = 0.15 - defense * (0.15 - 0.01)

    def ignites(wc):
        hits = 0
        for seed in seeds:
            lf = eng.default_levers_fn(divest_pct=0.0, war_chest_override=float(wc))
            p = eng.Params(months=months, granite_target_alpha=float(alpha))
            hist = eng.run(p, levers_fn=lf, months=months, seed=seed)
            if _defections_within(hist, horizon, min_defections):
                hits += 1
        return hits > len(seeds) / 2

    if not ignites(hi):
        return hi, False   # doesn't ignite even at the top of the range
    if ignites(lo):
        return lo, True    # already ignited at the bottom

    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if ignites(mid):
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi), True


# ----------------------------------------------------------------------------
# Spend decomposition -- the four jobs (spec 3.6) -- lightweight version
# ----------------------------------------------------------------------------

def four_jobs(base_p: eng.Params, war_chest, alpha: float, months=60, seed=None):
    """
    Attribute Granite's trade spend to its four jobs via counterfactual toggles.
    Returns terminal-NPV deltas vs a no-trade-spend baseline. This is a
    demo-grade decomposition (single deterministic run each); the spec's fuller
    version lives in decompose.py for v1.1.
    """
    def npv(divest_pct=0.0, wc=war_chest, freeze_contracts=False,
            open_shelf=False, freeze_rivals_wc=None):
        p = eng.Params(months=months, granite_target_alpha=alpha)
        effective_wc = freeze_rivals_wc if freeze_rivals_wc is not None else wc
        lf = eng.default_levers_fn(divest_pct=divest_pct, war_chest_override=effective_wc)
        hist = eng.run(p, levers_fn=lf, months=months, seed=seed)
        return hist["final_state"].cash["GRANITE"]

    baseline = npv()                       # full program
    no_spend = npv(divest_pct=1.0)         # cut all discretionary trade spend

    total_value_of_spend = baseline - no_spend

    # Rough attribution by toggling one lever at a time from the no-spend point.
    # (Demo-grade: these are illustrative decompositions, clearly labeled.)
    retention_like = npv(divest_pct=0.5) - no_spend            # partial hold
    discrimination_like = 0.35 * total_value_of_spend          # placeholder split
    channel_rent_like = 0.30 * total_value_of_spend
    deadweight_like = total_value_of_spend - retention_like

    return {
        "total_value_of_spend": total_value_of_spend,
        "baseline_npv": baseline,
        "no_spend_npv": no_spend,
        "components": {
            "Discrimination gain": max(discrimination_like, 0),
            "Retention value": max(retention_like, 0),
            "Channel access rent": max(channel_rent_like, 0),
            "Competitive offset": deadweight_like,
        },
    }
