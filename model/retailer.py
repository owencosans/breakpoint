"""
TOLLGATE v1.1 -- Structural retailer P&L.

Replaces the reduced-form outside option (competing bid + drift x decline)
with an actual dealer profit-and-loss comparison. For each channel c at each
month, we compute two worlds:

  STAY   -- on the Granite contract: receive Granite's payment W_c, accept a
            capped margin on Granite brands (price/plan compliance), Granite's
            visibility floor holds, and rivals' allowed spend in the store is
            capped -- which also caps how much RIVAL money the dealer can
            harvest.
  DEFECT -- off contract: no Granite payment, full open margins on everything,
            open Tullock visibility (Granite volume decays), all rival dealer
            money uncapped, AND the dealer can reallocate legacy floor space /
            rep-hours toward the growth format when its $/slot overtakes the
            legacy $/slot.

The outside option is then DERIVED:

    O_c = (defect operating P&L) - (stay operating P&L excl. W) - s_c

so the participation interface in mechanics.py (defect_probability,
min_viable_payment) is unchanged -- only its content is now structural. The
old drift emerges for the right reason: as the legacy format melts, the
reallocation option on legacy-heavy floor space (Hartline) appreciates; as an
entrant surges, the uncapped-rival-money term (Nova) jumps.

Units: index $/month, consistent with engine cash accounting (1 consumer =
1 unit/month of demand).
"""

from __future__ import annotations
import numpy as np

import mechanics as mech
import engine as eng


# ----------------------------------------------------------------------------
# Channel-level volumes and visibilities
# ----------------------------------------------------------------------------

def channel_format_volumes(pop: np.ndarray, p, c: int):
    """Format volume flowing through channel c: legacy and modern totals
    weighted by where each format's volume goes (spec: category-split
    channel weights)."""
    legacy_total = float(pop[:, eng.LEGACY_BRANDS].sum())
    modern_total = float(pop[:, eng.MODERN_BRANDS].sum())
    return legacy_total * p.channel_weight_legacy[c], modern_total * p.channel_weight_modern[c]


def channel_visibilities(trade_bid: np.ndarray, held: bool, p, c: int,
                         granite_defect_bid: float | None = None):
    """Within-channel visibility shares for both formats, under a given
    contract status. For the DEFECT counterfactual, Granite's legacy bid is
    replaced with its residual open-market bid (decoupled from the W being
    negotiated, to avoid circularity)."""
    b_select = trade_bid[eng.BI["GRANITE_SELECT"], c]
    if granite_defect_bid is not None:
        b_select = granite_defect_bid
    leg = mech.legacy_visibility(b_select, trade_bid[eng.BI["BOWERS"], c], held, p.v_floor)
    mod = mech.modern_visibility(
        trade_bid[eng.BI["GRANITE_ONE"], c], trade_bid[eng.BI["BOWER_FRESH"], c],
        trade_bid[eng.BI["NORD"], c], held, p.rival_modern_bid_cap,
    )
    return leg, mod   # leg: [select, bowers]; mod: [one, fresh, nord]


# ----------------------------------------------------------------------------
# The P&L itself
# ----------------------------------------------------------------------------

def dealer_pnl(pop: np.ndarray, trade_bid: np.ndarray, p, c: int,
               world: str, granite_payment: float = 0.0):
    """
    Monthly operating P&L for channel c's dealer in one world ('stay'|'defect').
    Returns a component dict; 'total' includes granite_payment only in 'stay'.
    """
    stay = (world == "stay")
    L_c, M_c = channel_format_volumes(pop, p, c)
    leg_vis, mod_vis = channel_visibilities(
        trade_bid, held=stay, p=p, c=c,
        granite_defect_bid=None if stay else 0.5 * p.W_c0[c],
    )

    m = p.retail_margin_open
    cap = p.contract_margin_cap if stay else 1.0

    # --- margin income by brand ---
    vol = {
        "GRANITE_SELECT": L_c * leg_vis[0],
        "BOWERS": L_c * leg_vis[1],
        "GRANITE_ONE": M_c * mod_vis[0],
        "BOWER_FRESH": M_c * mod_vis[1],
        "NORD": M_c * mod_vis[2],
    }
    margin_granite = (vol["GRANITE_SELECT"] * m[eng.BI["GRANITE_SELECT"]] +
                      vol["GRANITE_ONE"] * m[eng.BI["GRANITE_ONE"]]) * cap
    margin_rivals = (vol["BOWERS"] * m[eng.BI["BOWERS"]] +
                     vol["BOWER_FRESH"] * m[eng.BI["BOWER_FRESH"]] +
                     vol["NORD"] * m[eng.BI["NORD"]])

    # --- manufacturer money the dealer harvests ---
    # Under contract, rival modern spend in the store is capped -- the dealer
    # collects only the allowed fraction. Off contract, all of it.
    rival_cap = p.rival_modern_bid_cap if stay else 1.0
    payments_rivals = (trade_bid[eng.BI["BOWERS"], c]
                       + rival_cap * (trade_bid[eng.BI["BOWER_FRESH"], c]
                                      + trade_bid[eng.BI["NORD"], c]))
    payments_granite = granite_payment if stay else 0.0

    # --- space reallocation option (defect only) ---
    # $/slot by format; when the growth format out-earns the legacy slot, a
    # defected dealer converts k_realloc of its legacy footage/rep-hours.
    legacy_slots = max(p.slots_c[c] * p.legacy_slot_frac_c[c], 1e-6)
    modern_slots = max(p.slots_c[c] - legacy_slots, 1e-6)
    legacy_rev_open = (vol["GRANITE_SELECT"] * m[eng.BI["GRANITE_SELECT"]] +
                       vol["BOWERS"] * m[eng.BI["BOWERS"]])
    modern_rev_open = (vol["GRANITE_ONE"] * m[eng.BI["GRANITE_ONE"]] +
                       vol["BOWER_FRESH"] * m[eng.BI["BOWER_FRESH"]] +
                       vol["NORD"] * m[eng.BI["NORD"]])
    per_slot_legacy = legacy_rev_open / legacy_slots
    per_slot_modern = modern_rev_open / modern_slots
    realloc_gain = 0.0
    if not stay:
        realloc_gain = p.k_realloc * legacy_slots * max(0.0, per_slot_modern - per_slot_legacy)

    total = margin_granite + margin_rivals + payments_rivals + payments_granite + realloc_gain
    return {
        "margin_granite": margin_granite,
        "margin_rivals": margin_rivals,
        "payments_granite": payments_granite,
        "payments_rivals": payments_rivals,
        "realloc_gain": realloc_gain,
        "per_slot_legacy": per_slot_legacy,
        "per_slot_modern": per_slot_modern,
        "total": total,
    }


def structural_outside_option(pop: np.ndarray, trade_bid: np.ndarray, p) -> np.ndarray:
    """
    O_c = defect operating P&L - stay operating P&L (excl. Granite payment)
          - switching cost s_c.
    The payment W then competes against O through the unchanged participation
    machinery: dealer stays iff W >= O (plus bluff noise).
    """
    s_c = p.stickiness_factor * p.W_c0
    O = np.zeros(eng.N_CHANNELS)
    for c in range(eng.N_CHANNELS):
        stay0 = dealer_pnl(pop, trade_bid, p, c, "stay", granite_payment=0.0)
        defect = dealer_pnl(pop, trade_bid, p, c, "defect")
        O[c] = defect["total"] - stay0["total"] - s_c[c]
    return O


def pnl_timeseries(hist: dict, p) -> dict:
    """
    Replay a run's history into per-channel stay/defect P&L component arrays
    for the Dealer P&L tab. Requires hist['trade_bid'] (captured by engine.run)
    plus pop, granite_pay. Returns nested dict:
      out[channel_name] = { 'stay': [T,...], 'defect': [...], components... }
    """
    T = len(hist["t"])
    s_all = p.stickiness_factor * p.W_c0
    out = {}
    for cname, c in eng.CI.items():
        rows_stay, rows_defect = [], []
        slots_l, slots_m = [], []
        for t in range(T):
            pop = hist["pop"][t]
            tb = hist["trade_bid"][t]
            wpay = hist["granite_pay"][t, c]
            s = dealer_pnl(pop, tb, p, c, "stay", granite_payment=wpay)
            d = dealer_pnl(pop, tb, p, c, "defect")
            rows_stay.append(s)
            rows_defect.append(d)
            slots_l.append(s["per_slot_legacy"])
            slots_m.append(s["per_slot_modern"])
        out[cname] = {
            "stay_total": np.array([r["total"] for r in rows_stay]),
            "defect_total": np.array([r["total"] for r in rows_defect]),
            "stay_components": rows_stay,
            "defect_components": rows_defect,
            "per_slot_legacy": np.array(slots_l),
            "per_slot_modern": np.array(slots_m),
            "switching_cost": float(s_all[c]),
        }
        # Decision-relevant premium: what the dealer nets by defecting, AFTER
        # the switching cost and AFTER the payment it would forfeit. Positive
        # = defection is rational under the current payment policy. Its
        # zero-crossing is the ECONOMIC T*.
        prem = (out[cname]["defect_total"] - s_all[c]) - out[cname]["stay_total"]
        out[cname]["defection_premium"] = prem
        cross = np.argmax(prem > 0) if (prem > 0).any() else None
        out[cname]["economic_T_star"] = int(cross) if cross is not None and prem[cross] > 0 else None
    return out


def flex_slot_whatif(pop: np.ndarray, trade_bid: np.ndarray, p, c: int,
                     extra_modern_slots: float = 2.0, cost_per_slot: float = 1.5):
    """
    'What would this dealer do with two more feet?' -- adds capacity dedicated
    to the growth format at a monthly cost, WITHOUT defecting. Returns the
    incremental monthly P&L. Analog of adding a counter rack / kiosk / rep:
    lumpy capacity, priced, diminishing (we take the CURRENT $/slot, which
    overstates slightly -- labeled illustrative in the UI).
    """
    snap = dealer_pnl(pop, trade_bid, p, c, "stay", granite_payment=0.0)
    gain = extra_modern_slots * snap["per_slot_modern"] - extra_modern_slots * cost_per_slot
    return {"gain": gain, "per_slot_modern": snap["per_slot_modern"],
            "cost": extra_modern_slots * cost_per_slot}
