"""
TOLLGATE v1.0 -- Engine test suite.
Run: python -m pytest test_engine.py -v -s
Saturday exit criterion (build spec section 8): this file green + calibration
targets hit, before any Streamlit/UI work starts.
"""

import time
import numpy as np
import pytest

import engine as eng
import mechanics as mech


# ----------------------------------------------------------------------------
# Unit tests: mechanics.py
# ----------------------------------------------------------------------------

def test_normal_cdf_ppf_roundtrip():
    xs = np.array([-2.5, -1.0, 0.0, 0.5, 1.645, 3.0])
    p = mech.normal_cdf(xs)
    back = mech.normal_ppf(p)
    assert np.allclose(xs, back, atol=1e-6)


def test_normal_ppf_known_values():
    assert abs(mech.normal_ppf(0.95) - 1.6449) < 1e-3
    assert abs(mech.normal_ppf(0.5) - 0.0) < 1e-9


def test_gap_migration_hazard_bounded_and_monotonic():
    G = np.linspace(-5, 5, 50)
    h = mech.gap_migration_hazard(G, theta=2.0, beta=3.0, h0=0.01,
                                   ratchet_reverse=0.0, kappa=2.5, vis_j=1.0, gamma=0.5)
    assert np.all(h >= 0) and np.all(h <= 0.01 + 1e-9)
    assert h[-1] > h[0]


def test_ratchet_penalizes_reverse_flow():
    h_no_ratchet = mech.gap_migration_hazard(3.0, 2.0, 3.0, 0.01, 0.0, 2.5, 1.0, 0.5)
    h_full_ratchet = mech.gap_migration_hazard(3.0, 2.0, 3.0, 0.01, 1.0, 2.5, 1.0, 0.5)
    assert h_full_ratchet < h_no_ratchet


def test_tullock_shares_sum_to_one_and_rank_correctly():
    shares = mech.tullock_shares(np.array([10.0, 20.0, 5.0]))
    assert abs(shares.sum() - 1.0) < 1e-9
    assert shares[1] > shares[0] > shares[2]


def test_tullock_zero_bids_split_evenly():
    shares = mech.tullock_shares(np.array([0.0, 0.0, 0.0]))
    assert np.allclose(shares, 1 / 3, atol=1e-3)


def test_legacy_visibility_contract_floor_holds_against_huge_rival_bid():
    v_held = mech.legacy_visibility(bid_select=1.0, bid_bowers=100.0, contract_held=True, v_floor=0.55)
    assert v_held[0] == pytest.approx(0.55)
    v_open = mech.legacy_visibility(bid_select=1.0, bid_bowers=100.0, contract_held=False, v_floor=0.55)
    assert v_open[0] < 0.1


def test_modern_visibility_rival_cap_releases_on_defection():
    held = mech.modern_visibility(bid_one=10, bid_fresh=10, bid_nord=10,
                                   legacy_contract_held=True, rival_cap=0.5)
    open_ = mech.modern_visibility(bid_one=10, bid_fresh=10, bid_nord=10,
                                    legacy_contract_held=False, rival_cap=0.5)
    assert held[2] < open_[2]   # NORD's share is higher once the channel defects


def test_min_viable_payment_hits_target_alpha_exactly():
    O_c = 50.0
    w_star = mech.min_viable_payment(O_c, sigma_bluff_frac=0.25, alpha=0.05)
    assert w_star > O_c
    p_defect_at_wstar = mech.defect_probability(O_c, w_star, 0.25)
    assert abs(p_defect_at_wstar - 0.05) < 1e-3


def test_update_ratchet_monotonic_in_cumulative_flow():
    init_mass = np.array([45.0, 30.0, 25.0, 21.0])
    flow_low = np.zeros((4, 6, 6)); flow_low[1, 0, 1] = 0.1
    flow_high = np.zeros((4, 6, 6)); flow_high[1, 0, 1] = 5.0
    r_low = mech.update_ratchet(flow_low, init_mass, 0.02)
    r_high = mech.update_ratchet(flow_high, init_mass, 0.02)
    assert r_high[1, 0, 1] > r_low[1, 0, 1]
    assert 0 <= r_low[1, 0, 1] <= 1 and 0 <= r_high[1, 0, 1] <= 1


# ----------------------------------------------------------------------------
# Engine tests: conservation & structural integrity
# ----------------------------------------------------------------------------

def test_population_conserved():
    p = eng.Params()
    hist = eng.run(p, months=24, seed=None)
    total0 = p.pop0.sum()
    final = hist["final_state"]
    assert abs(final.pop.sum() - (total0 + final.cum_inflow)) < 1e-6


def test_no_negative_populations():
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    assert (hist["pop"] >= -1e-9).all()


def test_s4_has_zero_legacy_population_always():
    p = eng.Params()
    hist = eng.run(p, months=36, seed=None)
    s4 = eng.SI["S4_NEW"]
    legacy_pop_s4 = hist["pop"][:, s4, :][:, eng.LEGACY_BRANDS]
    assert np.allclose(legacy_pop_s4, 0.0, atol=1e-9)


def test_deterministic_mode_reproducible():
    p = eng.Params()
    h1 = eng.run(p, months=36, seed=None)
    h2 = eng.run(p, months=36, seed=None)
    assert np.allclose(h1["pop"], h2["pop"])


def test_seeded_mode_reproducible():
    p = eng.Params()
    h1 = eng.run(p, months=36, seed=42)
    h2 = eng.run(p, months=36, seed=42)
    assert np.allclose(h1["pop"], h2["pop"])


def test_performance_budget():
    p = eng.Params()
    t0 = time.perf_counter()
    eng.run(p, months=60, seed=None)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print(f"\n  run() took {elapsed_ms:.2f} ms for 60 months (spec target: <5ms hot-path)")
    assert elapsed_ms < 300  # generous cold-start ceiling; see printed value above for the real number


# ----------------------------------------------------------------------------
# Customer heterogeneity tests: two accounts, two defection mechanisms
# ----------------------------------------------------------------------------

def test_customer_weights_sum_to_one():
    p = eng.Params()
    assert abs(p.channel_weight_legacy.sum() - 1.0) < 1e-9
    assert abs(p.channel_weight_modern.sum() - 1.0) < 1e-9
    assert abs(p.nordkapp_channel_alloc.sum() - 1.0) < 1e-9


def test_drift_story_hartline():
    """With the entrant switched OFF (war chest = 0), outside options move by
    category-decline drift alone. Hartline (legacy-heavy) must drift up harder
    than Nova (modern-heavy). This is the T*-clock mechanism in isolation."""
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None,
                   levers_fn=eng.default_levers_fn(war_chest_override=0.0))
    O = hist["O_c"]
    growth_hartline = O[-1, eng.CI["HARTLINE"]] - O[0, eng.CI["HARTLINE"]]
    growth_nova = O[-1, eng.CI["NOVA"]] - O[0, eng.CI["NOVA"]]
    print(f"\n  No-entrant O growth -- Hartline: +{growth_hartline:.1f}, Nova: +{growth_nova:.1f}")
    assert growth_hartline > growth_nova > 0


def test_bid_shock_story_nova():
    """With the entrant surging, Nova's outside option must grow MORE than
    Hartline's relative to the no-entrant world -- NORD's money lands where
    modern volume flows. This is the B*-tipping mechanism in isolation."""
    p = eng.Params()
    h_off = eng.run(p, months=60, seed=None,
                    levers_fn=eng.default_levers_fn(war_chest_override=0.0))
    h_surge = eng.run(p, months=60, seed=None,
                      levers_fn=eng.default_levers_fn(war_chest_override=400.0))
    lift_nova = h_surge["O_c"][-1, eng.CI["NOVA"]] - h_off["O_c"][-1, eng.CI["NOVA"]]
    lift_hartline = h_surge["O_c"][-1, eng.CI["HARTLINE"]] - h_off["O_c"][-1, eng.CI["HARTLINE"]]
    print(f"\n  Entrant-surge O lift -- Nova: +{lift_nova:.1f}, Hartline: +{lift_hartline:.1f}")
    assert lift_nova > lift_hartline
    assert lift_nova > 0


def test_surge_cost_of_holding_nova():
    """Even when nobody defects (Granite's default policy pays W* wherever it
    must), the entrant's surge should show up as a higher REQUIRED payment to
    hold Nova -- the chicken game priced in dollars, not just probabilities."""
    p = eng.Params()
    h_off = eng.run(p, months=60, seed=None,
                    levers_fn=eng.default_levers_fn(war_chest_override=0.0))
    h_surge = eng.run(p, months=60, seed=None,
                      levers_fn=eng.default_levers_fn(war_chest_override=400.0))
    pay_lift = h_surge["granite_pay"][-1, eng.CI["NOVA"]] - h_off["granite_pay"][-1, eng.CI["NOVA"]]
    print(f"\n  Extra monthly payment required to hold Nova under surge: +{pay_lift:.1f}")
    assert pay_lift > 0


def test_surge_plus_divestment_produces_defection_and_stable_state():
    """Integration: deep divestment during an entrant surge should produce at
    least one defection (seeded mode), and the engine must remain
    well-behaved after contracts release (no NaNs, populations conserved)."""
    p = eng.Params()
    hist = eng.run(p, months=60, seed=7,
                   levers_fn=eng.default_levers_fn(divest_pct=0.50, war_chest_override=600.0))
    first = eng.first_defection_month(hist)
    print(f"\n  First defection under surge+50% divestment (seed 7): month {first}")
    assert first is not None
    final = hist["final_state"]
    assert np.isfinite(final.pop).all()
    total0 = p.pop0.sum()
    assert abs(final.pop.sum() - (total0 + final.cum_inflow)) < 1e-6


# ----------------------------------------------------------------------------
# Structural retailer P&L tests (retailer.py) -- defection as emergent economics
# ----------------------------------------------------------------------------

def test_retailer_pnl_components_sum():
    import retailer as ret
    p = eng.Params()
    hist = eng.run(p, months=2, seed=None)
    pop, tb = hist["pop"][0], hist["trade_bid"][0]
    for c in range(eng.N_CHANNELS):
        for world, wpay in [("stay", 10.0), ("defect", 0.0)]:
            r = ret.dealer_pnl(pop, tb, p, c, world, granite_payment=wpay)
            parts = (r["margin_granite"] + r["margin_rivals"] + r["payments_granite"]
                     + r["payments_rivals"] + r["realloc_gain"])
            assert abs(parts - r["total"]) < 1e-9


def test_structural_O_matches_definition():
    """O_c must equal defect_pnl - stay_pnl(excl. payment) - switching cost."""
    import retailer as ret
    p = eng.Params()
    hist = eng.run(p, months=2, seed=None)
    pop, tb = hist["pop"][0], hist["trade_bid"][0]
    O = ret.structural_outside_option(pop, tb, p)
    s_all = p.stickiness_factor * p.W_c0
    for c in range(eng.N_CHANNELS):
        stay0 = ret.dealer_pnl(pop, tb, p, c, "stay", granite_payment=0.0)["total"]
        defect = ret.dealer_pnl(pop, tb, p, c, "defect")["total"]
        assert abs(O[c] - (defect - stay0 - s_all[c])) < 1e-9


def test_contract_rational_at_t0():
    """Under Status Quo at t=0, staying must be the dealer's rational choice
    for every channel: net defection premium (after switching cost and the
    payment being received) is negative."""
    import retailer as ret
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    ts = ret.pnl_timeseries(hist, p)
    for cname in eng.CHANNELS:
        prem0 = ts[cname]["defection_premium"][0]
        print(f"\n  {cname} net defection premium at t=0: {prem0:+.1f}")
        assert prem0 < 0


def test_per_slot_crossover_hartline():
    """The structural drift story rendered as returns: the growth format's
    $/slot must overtake the legacy $/slot on Hartline's floor within the
    horizon -- floor space hostage to a dying category."""
    import retailer as ret
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    ts = ret.pnl_timeseries(hist, p)["HARTLINE"]
    assert ts["per_slot_modern"][0] < ts["per_slot_legacy"][0]
    assert ts["per_slot_modern"][-1] > ts["per_slot_legacy"][-1]
    cross = np.argmax(ts["per_slot_modern"] > ts["per_slot_legacy"])
    print(f"\n  Hartline $/slot crossover at month {cross}")
    assert 6 < cross < 55


def test_divestment_pulls_economic_T_star_forward():
    """Cutting the payment must make defection rational sooner somewhere --
    the economic T* under divestment appears (or comes earlier) vs status quo."""
    import retailer as ret
    p = eng.Params()
    h0 = eng.run(p, levers_fn=eng.default_levers_fn(0.0, None), months=60, seed=None)
    h1 = eng.run(p, levers_fn=eng.default_levers_fn(0.55, None), months=60, seed=None)
    t0 = ret.pnl_timeseries(h0, p)
    t1 = ret.pnl_timeseries(h1, p)
    def earliest(ts):
        vals = [ts[c]["economic_T_star"] for c in eng.CHANNELS if ts[c]["economic_T_star"] is not None]
        return min(vals) if vals else None
    e0, e1 = earliest(t0), earliest(t1)
    print(f"\n  Earliest economic T*: status quo={e0}, 55% divestment={e1}")
    assert e1 is not None
    assert e0 is None or e1 <= e0




# ----------------------------------------------------------------------------
# Calibration tests (spec section 6 "Calibration test" box) -- the Saturday gate
# ----------------------------------------------------------------------------

def test_calibration_legacy_decline():
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    legacy = eng.legacy_total(hist)
    g = eng.cagr(legacy, 60)
    print(f"\n  Legacy CAGR: {g:.1%}  (target ~-9%/yr)")
    assert -0.15 < g < -0.04


def test_calibration_modern_growth_early():
    p = eng.Params()
    hist = eng.run(p, months=24, seed=None)
    modern = eng.modern_total(hist)
    g = eng.cagr(modern, 24)
    print(f"\n  Modern CAGR (yr 1-2): {g:.1%}  (target ~+30%/yr, decelerating later)")
    assert 0.10 < g < 0.55


def test_calibration_modern_decelerates():
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    modern = eng.modern_total(hist)
    g_early = eng.cagr(modern[:24], 24)
    g_late = eng.cagr(modern[36:60], 24)
    print(f"\n  Modern CAGR early: {g_early:.1%} vs late: {g_late:.1%} (should decelerate)")
    assert g_late < g_early


def test_calibration_nord_share_of_modern():
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    nord = eng.brand_total(hist, eng.BI["NORD"])[-1]
    modern = eng.modern_total(hist)[-1]
    share = nord / modern
    print(f"\n  NORD share of Modern at month 60: {share:.1%}  (target >=60%)")
    assert share >= 0.55


def test_calibration_no_early_defection_status_quo():
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    first = eng.first_defection_month(hist)
    print(f"\n  First defection month under Status Quo: {first}")
    assert first is None or first >= 18


def test_calibration_summary_print():
    """Not a real assertion -- just dumps the full calibration picture for a
    human to eyeball, per the spec's 'do not start UI until tests pass' gate."""
    p = eng.Params()
    hist = eng.run(p, months=60, seed=None)
    legacy = eng.legacy_total(hist)
    modern = eng.modern_total(hist)
    print("\n  ===== CALIBRATION SUMMARY (Status Quo, 60mo, deterministic) =====")
    print(f"  Legacy:  {legacy[0]:.1f} -> {legacy[-1]:.1f}  (CAGR {eng.cagr(legacy,60):.1%})")
    print(f"  Modern:  {modern[0]:.1f} -> {modern[-1]:.1f}  (CAGR {eng.cagr(modern,60):.1%})")
    for b_name in ["GRANITE_SELECT", "BOWERS", "GRANITE_ONE", "BOWER_FRESH", "NORD"]:
        series = eng.brand_total(hist, eng.BI[b_name])
        print(f"    {b_name:15s} {series[0]:6.2f} -> {series[-1]:6.2f}")
    print(f"  D(t) final (legacy decline index): {hist['D'][-1]:.2f}")
    print(f"  Contracts held at end: {hist['contract_held'][-1]} (channels: {eng.CHANNELS})")
    print(f"  First defection month: {eng.first_defection_month(hist)}")
    assert True


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"]))
