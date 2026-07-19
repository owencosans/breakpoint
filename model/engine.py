"""
BREAKPOINT model -- Simulation Engine
Params, MarketState, step(), run(). See the build spec
sections 1-3 and 6.

SCOPE NOTE: this file plus mechanics.py are the Saturday deliverable
("engine + mechanics + tests green; hit calibration targets" -- spec section
8). The default policy functions below (default_levers_fn, covering Granite/
Bower/Nordkapp) are the minimal Status-Quo behavior needed to make run()
executable and testable today. Player-lever wiring, the four scenario
presets, the four-jobs counterfactual toggles, and the war-chest sweep
belong in policies.py / presets.py / decompose.py / sweep.py on Sunday per
the spec's file structure (section 7) -- treat the policy logic here as the
seed those files will extend and refactor out, not the final API.

MODELING NOTE on visibility: the spec's State object lists pop[s,b] (no
channel dimension) alongside V[b,c] (channel-resolved). This engine follows
that literally: population/migration is segment-resolved but not
channel-resolved, so each step collapses the three channels' Tullock
contests into one volume-weighted visibility scalar per brand
(_aggregate_visibility) before it enters the segment-level hazard function.
Fully channel-resolved consumer paths (segment x channel population) are a
v1.1 item, noted in the spec's backlog.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Optional
import numpy as np

import mechanics as mech

# ============================================================================
# 1. MARKET STRUCTURE  (spec section 1)
# ============================================================================

BRANDS = ["GRANITE_SELECT", "BOWERS", "GRANITE_ONE", "BOWER_FRESH", "NORD", "OUT"]
N_BRANDS = len(BRANDS)
BI = {name: i for i, name in enumerate(BRANDS)}

LEGACY_BRANDS = [BI["GRANITE_SELECT"], BI["BOWERS"]]
MODERN_BRANDS = [BI["GRANITE_ONE"], BI["BOWER_FRESH"], BI["NORD"]]
OUT = BI["OUT"]
REAL_BRANDS = LEGACY_BRANDS + MODERN_BRANDS  # excludes OUT

HOUSES = ["GRANITE", "BOWER", "NORDKAPP"]
HOUSE_OF_BRAND = {
    BI["GRANITE_SELECT"]: "GRANITE", BI["GRANITE_ONE"]: "GRANITE",
    BI["BOWERS"]: "BOWER",           BI["BOWER_FRESH"]: "BOWER",
    BI["NORD"]: "NORDKAPP",
}

SEGMENTS = ["S1_LOYAL", "S2_VALUE", "S3_CURIOUS", "S4_NEW"]
N_SEGMENTS = len(SEGMENTS)
SI = {name: i for i, name in enumerate(SEGMENTS)}

CHANNELS = ["HARTLINE", "NOVA", "INDIES"]
N_CHANNELS = len(CHANNELS)
CI = {name: i for i, name in enumerate(CHANNELS)}

# Retail customer characters (spec section 1 archetypes, made concrete for the
# sales-force audience). Two featured accounts with OPPOSITE exposure to the
# legacy/modern transition, plus an independents bucket:
#   HARTLINE -- large dealer chain over-indexed in LEGACY (contract plans).
#              Their defection risk is a DRIFT story: the category melts under
#              their floor space, so their outside option climbs slowly and
#              relentlessly. They are the T* clock.
#   NOVA     -- retail partner over-indexed in NEW BUSINESS (digital eSIM
#              activations). Their defection risk is a BID-SHOCK story: the
#              entrant's money lands hardest where modern volume flows. They
#              are the B* tipping wire.
#   INDIES   -- independent dealer aggregate; mixed book, lowest stickiness,
#              first to flip on pure price.
CUSTOMERS = {
    "HARTLINE": {
        "display": "Hartline Communications (dealer chain)",
        "legacy_mix": 0.75,
        "blurb": "Big, loyal, legacy-heavy. Doesn't want to leave -- watches the backroom economics decay.",
    },
    "NOVA": {
        "display": "Nova Mobile Retail",
        "legacy_mix": 0.35,
        "blurb": "Growth-format book. Loyalty is real but rented -- every entrant offer gets a meeting.",
    },
    "INDIES": {
        "display": "Independent dealers (aggregate)",
        "legacy_mix": 0.55,
        "blurb": "Fragmented, price-led, low switching costs. The canary channel.",
    },
}

# Display-layer skin (telecom). Code keys stay stable; UI uses these labels.
DISPLAY_NAMES = {
    "GRANITE_SELECT": "Granite Select (contract plan)",
    "BOWERS": "Bower Basic (contract plan)",
    "GRANITE_ONE": "Granite One (digital eSIM)",
    "BOWER_FRESH": "Bower Flex (digital eSIM)",
    "NORD": "NORD (digital eSIM)",
    "OUT": "Lapsed / no service",
}
FORMAT_LABELS = {"legacy": "Contract plans (dealer channel)", "modern": "Digital eSIM plans"}


def _build_reachability() -> np.ndarray:
    """R[s,i,j]: dampening on raw hazard, encoding spec section 1's
    reachable-moves table. 0 = structurally blocked, 1 = full strength.
    OUT is handled separately via exit_hazard, not represented here."""
    R = np.zeros((N_SEGMENTS, N_BRANDS, N_BRANDS))

    s1 = SI["S1_LOYAL"]
    for i in LEGACY_BRANDS:
        for j in LEGACY_BRANDS:
            if i != j:
                R[s1, i, j] = 0.10  # "exit only; tiny migration"

    s2 = SI["S2_VALUE"]
    for i in LEGACY_BRANDS:
        for j in LEGACY_BRANDS:
            if i != j:
                R[s2, i, j] = 1.00  # "down-trade Legacy<->Legacy"
    for i in LEGACY_BRANDS:
        for j in MODERN_BRANDS:
            R[s2, i, j] = 0.40      # "some -> Modern value"

    s3 = SI["S3_CURIOUS"]
    for i in LEGACY_BRANDS:
        for j in MODERN_BRANDS:
            R[s3, i, j] = 1.00      # defining behavior: Legacy -> Modern
    for i in LEGACY_BRANDS:
        for j in LEGACY_BRANDS:
            if i != j:
                R[s3, i, j] = 0.20
    for i in MODERN_BRANDS:
        for j in MODERN_BRANDS:
            if i != j:
                R[s3, i, j] = 0.50  # "some Modern<->Modern"

    s4 = SI["S4_NEW"]
    for i in MODERN_BRANDS:
        for j in MODERN_BRANDS:
            if i != j:
                R[s4, i, j] = 1.00  # "Modern <-> Modern ONLY"

    return R


REACHABILITY = _build_reachability()


# ============================================================================
# 2. PARAMETERS  (spec section 6 defaults; [v] = flagged for Monday verify)
# ============================================================================

@dataclass
class Params:
    # ---- t=0 reference prices, $/unit index (spec section 6 P_net figures) ----
    P_list0: np.ndarray = field(default_factory=lambda: np.array([
        5.60,  # GRANITE_SELECT
        3.40,  # BOWERS
        5.20,  # GRANITE_ONE
        4.90,  # BOWER_FRESH
        5.80,  # NORD
        0.0,   # OUT (unused)
    ]))
    unit_cost_pct: float = 0.18  # high-margin legacy format: cost as % of list

    # ---- t=0 population, index units (spec section 1/6: Legacy=100, Modern=35) ----
    pop0: np.ndarray = field(default_factory=lambda: np.array([
        # GRANITE_SELECT  BOWERS  GRANITE_ONE  BOWER_FRESH  NORD    OUT
        [29.25,           15.75,  0.00,        0.00,        0.00,  0.0],  # S1 Loyal   (45)
        [12.00,           18.00,  0.00,        0.00,        0.00,  0.0],  # S2 Value   (30)
        [13.75,           11.25,  2.80,        2.00,        9.20,  0.0],  # S3 Curious (25 legacy + 14 modern)
        [ 0.00,            0.00,  4.20,        3.00,        13.80, 0.0],  # S4 New     (21 modern; pre-existing pool)
    ]))

    # ---- segment hazard params: theta($), beta(/$), h0(frac/mo) ----
    # theta[S3_CURIOUS] is deliberately NEGATIVE: spec section 1 defines this
    # segment's move as "visibility + trial driven," not price-driven -- and
    # Modern is priced at a premium to Legacy (G is structurally negative for
    # Legacy->Modern flows), so a positive theta would gate S3's defining
    # behavior almost fully shut. A negative theta means S3 will cross into
    # Modern despite a several-dollar premium, gated mainly by vis_j**gamma.
    theta: np.ndarray = field(default_factory=lambda: np.array([4.50, 2.90, -2.50, 1.20]))
    beta: np.ndarray = field(default_factory=lambda: np.array([2.00, 3.00, 2.50, 2.20]))
    h0: np.ndarray = field(default_factory=lambda: np.array([0.0015, 0.0080, 0.0135, 0.0220]))
    kappa: float = 2.50            # ratchet premium multiplier (spec 3.1)
    gamma_vis: float = 0.50        # visibility gate exponent

    # ---- exit hazard: e0 (frac/mo), a (baseline attrition frac/mo), eta ----
    exit_e0: np.ndarray = field(default_factory=lambda: np.array([0.0015, 0.0035, 0.0020, 0.0010]))
    exit_a: np.ndarray = field(default_factory=lambda: np.array([0.0100, 0.0060, 0.0030, 0.0020]))
    exit_eta: float = 0.25

    # ---- S4 inflow tap ----
    s4_N0: float = 0.55        # index units/month at t=0
    s4_g_annual: float = 0.15  # inflow itself grows -- category tailwind [v]
    s4_gamma: float = 0.35

    # ---- ratchet bookkeeping ----
    ratchet_scale: float = 0.02  # frac of segment's initial mass to ~fully ratchet

    # ---- retail customers (see CUSTOMERS metadata above) ----
    # Category-split volume weights: WHERE each format's volume actually flows.
    # This is what makes the two featured customers behave differently without
    # adding any population state: Hartline dominates legacy flow, Nova
    # dominates modern flow, Indies are mixed.
    channel_weight_legacy: np.ndarray = field(default_factory=lambda: np.array([0.50, 0.25, 0.25]))
    channel_weight_modern: np.ndarray = field(default_factory=lambda: np.array([0.20, 0.55, 0.25]))
    W_c0: np.ndarray = field(default_factory=lambda: np.array([60.0, 45.0, 25.0]))  # baseline trade $, index/mo
    stickiness_factor: np.ndarray = field(default_factory=lambda: np.array([0.35, 0.15, 0.05]))  # -> s_c

    # ---- structural dealer P&L (retailer.py) ----
    # Open-market retail margin per unit by brand (index $/unit/mo). Telecom
    # skin: blended monthly commission/residual per active line + attach.
    retail_margin_open: np.ndarray = field(default_factory=lambda: np.array([
        0.95,  # GRANITE_SELECT -- premium legacy carries the fattest penny profit
        0.70,  # BOWERS
        0.75,  # GRANITE_ONE
        0.70,  # BOWER_FRESH
        0.85,  # NORD
        0.0,   # OUT
    ]))
    # Contract compliance caps the dealer's margin on Granite brands (that cap
    # is what the payment W compensates). 0.60 = dealer keeps 60% of open margin.
    contract_margin_cap: float = 0.60
    # Fixed selling capacity per channel (floor space + rep-hours, in "slots"),
    # and the fraction of it planogrammed to the legacy format under contract
    # (mirrors each customer's legacy mix).
    slots_c: np.ndarray = field(default_factory=lambda: np.array([12.0, 9.0, 6.0]))
    legacy_slot_frac_c: np.ndarray = field(default_factory=lambda: np.array([0.75, 0.35, 0.55]))
    # Off contract, the dealer can convert this fraction of legacy slots to the
    # growth format when modern $/slot exceeds legacy $/slot.
    k_realloc: float = 0.50

    # DEPRECATED (superseded by structural P&L in retailer.py; retained so old
    # notebooks don't break, no longer read by the engine):
    delta_c: np.ndarray = field(default_factory=lambda: np.array([1.00, 0.45, 0.80]))
    delta_scale: float = 40.0
    v_floor: float = 0.55         # spec section 6 contract floor V-bar
    rival_modern_bid_cap: float = 0.50
    # When Granite loses a channel's contract, that channel's shelf actively
    # works against Granite: its share of the base sees ELEVATED migration out
    # of Granite brands (rivals get endcaps, rep push, trial offers). This is
    # the teeth of the contract -- without it, losing a contract costs almost no
    # volume and divestment looks free. Multiplier on outbound-from-Granite
    # hazard, scaled by the defected channels' share of legacy volume.
    contract_loss_hazard_mult: float = 2.2
    sigma_bluff_frac: float = 0.25  # spec section 6
    reversal_premium: float = 0.40  # pi, spec section 6
    reset_month_mod: int = 11       # annual reset window (t % 12 == 11)

    # ---- Granite default policy ----
    granite_target_alpha: float = 0.05         # "pay at W* + buffer" default risk tolerance
    # Finite defense budget: Granite CANNOT reactively out-pay an entrant surge
    # in every channel at once. When desired payments (sum of W*) exceed this
    # cap, spend is rationed toward the highest-value-to-defend channels, and
    # the rest are left exposed to their defection probability. This cap is the
    # mechanism that makes the chicken game real -- without it the incumbent has
    # an unlimited perfectly-responsive budget and B* never exists. Expressed as
    # a multiple of baseline total trade spend sum(W_c0).
    granite_defense_budget_mult: float = 1.35
    granite_legacy_modern_split: float = 0.80  # 80/20 default (spec section 4)
    granite_price_hike: float = 0.20           # $/hike
    granite_hike_months: tuple = (2, 8)        # two hikes/yr, spec section 4 default
    granite_promo_select0: float = 0.80        # $/unit
    granite_promo_one0: float = 0.10
    granite_one_gap_to_nord: float = 0.20      # modest, stable follower discount vs NORD

    # ---- Bower default policy ----
    bower_target_gap: float = 2.20    # spec section 6 "managed premium-value gap"
    bower_promo_match: float = 0.70   # matches Granite promo escalations at 70%
    bower_fresh_gap_to_nord: float = 0.90
    bower_fresh_cash_share: float = 0.20  # cross-subsidy of Bower Fresh shelf bids
    bower_channel_bid_rate: float = 0.30  # x W_c0, steady legacy-side rival pressure

    # ---- Nordkapp default (peacetime) policy ----
    nordkapp_base_rate: float = 88.0   # index $/mo, PEACETIME war chest (<< invasion B)
    nordkapp_reinvest_annual: float = 0.14  # leader reinvests as the category grows [v]
    nordkapp_shelf_share: float = 0.60
    nordkapp_promo_share: float = 0.40
    # NORD aims its dealer money where digital volume flows: Nova first.
    nordkapp_channel_alloc: np.ndarray = field(default_factory=lambda: np.array([0.20, 0.55, 0.25]))
    nordkapp_promo_cap: float = 0.50   # max $/unit price reduction

    # ---- economics ----
    discount_rate_annual: float = 0.10
    months: int = 60


# ============================================================================
# 3. STATE
# ============================================================================

@dataclass
class MarketState:
    t: int
    pop: np.ndarray             # [S, B]
    cum_flow: np.ndarray        # [S, B, B] cumulative migrated mass, for ratchet
    ratchet: np.ndarray         # [S, B, B] derived each step from cum_flow
    P_list: np.ndarray          # [B] current list price
    promo_subsidy: np.ndarray   # [B] current promo subsidy
    contract_held: np.ndarray   # [C] bool, Granite holds channel c's contract
    D: float                    # cumulative legacy decline index
    legacy0: float               # legacy total at t=0, for D(t)
    cash: dict                  # house -> cumulative discounted profit
    cum_inflow: float = 0.0     # S4 cumulative injected mass (conservation check)


def init_state(p: Params) -> MarketState:
    return MarketState(
        t=0,
        pop=p.pop0.copy(),
        cum_flow=np.zeros((N_SEGMENTS, N_BRANDS, N_BRANDS)),
        ratchet=np.zeros((N_SEGMENTS, N_BRANDS, N_BRANDS)),
        P_list=p.P_list0.copy(),
        promo_subsidy=np.zeros(N_BRANDS),
        contract_held=np.ones(N_CHANNELS, dtype=bool),
        D=0.0,
        legacy0=float(p.pop0[:, LEGACY_BRANDS].sum()),
        cash={h: 0.0 for h in HOUSES},
    )


# ============================================================================
# 4. DEFAULT (STATUS-QUO) POLICIES
#    Return a "levers" dict consumed by step(). See module docstring re: scope.
# ============================================================================

def _aggregate_visibility(trade_bid: np.ndarray, contract_held: np.ndarray, p: Params) -> np.ndarray:
    """Collapse the three customers' Tullock contests into one volume-weighted
    visibility scalar per brand -- see module docstring, MODELING NOTE.
    Weights are CATEGORY-SPLIT: legacy-format visibility is weighted by where
    legacy volume flows (Hartline-heavy), modern-format visibility by where
    modern volume flows (Nova-heavy). A defection therefore matters most in
    the channel that carries that format's volume -- e.g. losing Nova releases
    NORD's visibility exactly where digital activations happen."""
    vis = np.zeros(N_BRANDS)
    wl = p.channel_weight_legacy
    wm = p.channel_weight_modern
    for c in range(N_CHANNELS):
        held = bool(contract_held[c])
        leg = mech.legacy_visibility(
            trade_bid[BI["GRANITE_SELECT"], c], trade_bid[BI["BOWERS"], c], held, p.v_floor,
        )
        mod = mech.modern_visibility(
            trade_bid[BI["GRANITE_ONE"], c], trade_bid[BI["BOWER_FRESH"], c],
            trade_bid[BI["NORD"], c], held, p.rival_modern_bid_cap,
        )
        vis[BI["GRANITE_SELECT"]] += wl[c] * leg[0]
        vis[BI["BOWERS"]] += wl[c] * leg[1]
        vis[BI["GRANITE_ONE"]] += wm[c] * mod[0]
        vis[BI["BOWER_FRESH"]] += wm[c] * mod[1]
        vis[BI["NORD"]] += wm[c] * mod[2]
    return vis


def default_levers_fn(divest_pct: float = 0.0, war_chest_override: Optional[float] = None) -> Callable:
    """
    Builds the Status-Quo levers_fn:
      - Granite pays at its target-risk W*_c(alpha), scaled by (1 - divest_pct)
        -- the knob Sunday's Divestment Frontier sweep turns against these
        tested mechanics.
      - Bower tracks a target gap off Granite Select (1-month lag) and
        matches promo escalations at 70% depth (spec section 4).
      - Nordkapp spends its war chest 60% shelf / 40% trial promo, biased
        toward A-Chains first (spec section 4). war_chest_override is the
        knob Sunday's Invasion sweep uses to push spend past B*.
    """

    def levers_fn(state: MarketState, p: Params, t: int):
        # ---- list prices ----
        P_list = state.P_list.copy()
        if t > 0 and (t % 12) in p.granite_hike_months:
            P_list[BI["GRANITE_SELECT"]] += p.granite_price_hike
        # Bower tracks last period's Granite Select price, 1-month lag, target gap
        P_list[BI["BOWERS"]] = max(0.5, state.P_list[BI["GRANITE_SELECT"]] - p.bower_target_gap)
        # NORD holds price (spec: competes on visibility and trial, not price)
        P_list[BI["NORD"]] = p.P_list0[BI["NORD"]]
        P_list[BI["BOWER_FRESH"]] = max(0.5, P_list[BI["NORD"]] - p.bower_fresh_gap_to_nord)
        # Granite One tracks NORD at a modest, STABLE follower discount -- a
        # first-party defensive follower, not a value fighter brand (that's
        # Bower Fresh's role). Tying it to NORD's price (rather than leaving
        # it flat while NORD's net price drifts via growing promo) prevents
        # an accidental, compounding price edge from letting the follower
        # out-migrate the stated category leader over a 5yr horizon.
        P_list[BI["GRANITE_ONE"]] = max(0.5, P_list[BI["NORD"]] - p.granite_one_gap_to_nord)

        # ---- promo subsidies ----
        promo = np.zeros(N_BRANDS)
        promo[BI["GRANITE_SELECT"]] = p.granite_promo_select0
        promo[BI["GRANITE_ONE"]] = p.granite_promo_one0
        promo[BI["BOWERS"]] = p.bower_promo_match * promo[BI["GRANITE_SELECT"]]
        promo[BI["BOWER_FRESH"]] = 0.20
        if war_chest_override is not None:
            r_B = war_chest_override
        else:
            r_B = p.nordkapp_base_rate * (1.0 + p.nordkapp_reinvest_annual) ** (t / 12.0)
        promo[BI["NORD"]] = min(p.nordkapp_promo_cap, (p.nordkapp_promo_share * r_B) / 100.0)

        # ---- rival trade bids (needed BEFORE O_c, which is now structural) ----
        bower_channel_bid = p.bower_channel_bid_rate * p.W_c0
        nord_shelf_total = p.nordkapp_shelf_share * r_B
        nord_channel_bid = nord_shelf_total * p.nordkapp_channel_alloc

        # provisional trade_bid with rivals only; Granite's own cells are filled
        # after its payment is set (its legacy bid doesn't enter O_c -- the
        # defect counterfactual uses a fixed residual bid, see retailer.py).
        trade_bid = np.zeros((N_BRANDS, N_CHANNELS))
        trade_bid[BI["BOWERS"], :] = bower_channel_bid
        trade_bid[BI["BOWER_FRESH"], :] = p.bower_fresh_cash_share * bower_channel_bid
        trade_bid[BI["NORD"], :] = nord_channel_bid

        # ---- STRUCTURAL outside option: derived from the dealer's stay-vs-
        # defect P&L (margins, volumes, harvested rival money, and the option
        # to reallocate legacy floor space to the growth format). See
        # retailer.structural_outside_option. This replaces the old reduced
        # form (competing bid + delta*D drift), which is what it now EXPLAINS.
        import retailer as ret
        O_c = ret.structural_outside_option(state.pop, trade_bid, p)

        # ---- Granite's payment: target W*(alpha), scaled by (1 - divest_pct) ----
        # W_target can go negative when O_c is deeply negative (a channel with
        # no real defection risk at all, e.g. a very sticky Hartline early on) --
        # floor at a small baseline so trade_bid never goes negative.
        W_target = np.maximum(
            mech.min_viable_payment(O_c, p.sigma_bluff_frac, p.granite_target_alpha),
            0.10 * p.W_c0,
        )
        desired = np.where(state.contract_held, W_target * (1.0 - divest_pct), 0.5 * W_target)

        # Finite defense budget (see granite_defense_budget_mult). If desired
        # spend exceeds the cap, ration toward the channels worth the most to
        # defend -- value ~ (margin-weighted volume the channel carries). Lower-
        # priority held channels get only partial payment and stay exposed.
        budget = p.granite_defense_budget_mult * float(p.W_c0.sum())
        if desired.sum() > budget and desired.sum() > 0:
            # defend-value weight: legacy-format carriers protect the high-margin
            # base, so weight by legacy-volume share + a floor.
            defend_value = p.channel_weight_legacy + 0.25
            priority = defend_value / defend_value.sum()
            # water-filling: allocate budget by priority but never above desired.
            alloc = np.minimum(desired, priority * budget)
            leftover = budget - alloc.sum()
            # distribute any leftover to still-underfunded channels by priority
            for _ in range(3):
                gap = desired - alloc
                need = gap > 1e-6
                if leftover <= 1e-6 or not need.any():
                    break
                w = priority * need
                w = w / w.sum()
                add = np.minimum(gap, w * leftover)
                alloc = alloc + add
                leftover = budget - alloc.sum()
            granite_pay = alloc
        else:
            granite_pay = desired

        # ---- fill Granite's cells into the assembled trade_bid ----
        trade_bid[BI["GRANITE_SELECT"], :] = p.granite_legacy_modern_split * granite_pay
        trade_bid[BI["GRANITE_ONE"], :] = (1 - p.granite_legacy_modern_split) * granite_pay

        return {
            "P_list": P_list,
            "promo_subsidy": promo,
            "trade_bid": trade_bid,
            "granite_pay": granite_pay,
            "O_c": O_c,
        }

    return levers_fn


# ============================================================================
# 5. STEP
# ============================================================================

def step(state: MarketState, p: Params, levers: dict, t: int,
         rng: Optional[np.random.Generator]) -> MarketState:
    P_list = levers["P_list"]
    promo = levers["promo_subsidy"]
    P_net = P_list - promo
    trade_bid = levers["trade_bid"]
    granite_pay = levers["granite_pay"]
    O_c = levers["O_c"]

    # ---- visibility (aggregated across channels; see _aggregate_visibility) ----
    vis = _aggregate_visibility(trade_bid, state.contract_held, p)
    modern_vis_total = vis[MODERN_BRANDS].sum()

    # ---- contract-loss exposure: share of legacy volume sitting in channels
    # Granite has LOST. Consumers in a defected channel migrate out of Granite
    # brands faster (the shelf now works against Granite). See
    # contract_loss_hazard_mult. exposure in [0,1]; 0 when all held.
    lost_mask = ~state.contract_held
    lost_legacy_share = float((p.channel_weight_legacy * lost_mask).sum())
    granite_exposure = 1.0 + (p.contract_loss_hazard_mult - 1.0) * lost_legacy_share

    GRANITE_BRANDS = [b for b in REAL_BRANDS if HOUSE_OF_BRAND[b] == "GRANITE"]

    # ---- migration hazards, all segments x all reachable brand pairs ----
    pop = state.pop.copy()
    flow = np.zeros((N_SEGMENTS, N_BRANDS, N_BRANDS))

    for s in range(N_SEGMENTS):
        for i in REAL_BRANDS:
            if pop[s, i] <= 0:
                continue
            row_hazard = np.zeros(N_BRANDS)
            for j in REAL_BRANDS:
                if i == j or REACHABILITY[s, i, j] <= 0:
                    continue
                G = P_net[i] - P_net[j]
                h = mech.gap_migration_hazard(
                    G, p.theta[s], p.beta[s], p.h0[s],
                    state.ratchet[s, j, i],   # reverse-pair lookup -- see mechanics.py docstring
                    p.kappa, vis[j], p.gamma_vis,
                )
                row_hazard[j] = h * REACHABILITY[s, i, j]

            # contract-loss exposure lifts migration OUT of Granite brands
            if i in GRANITE_BRANDS:
                row_hazard *= granite_exposure

            h_exit = mech.exit_hazard(P_net[i], p.P_list0[i], p.exit_eta, p.exit_e0[s], p.exit_a[s])
            row_hazard[OUT] = h_exit

            total_h = row_hazard.sum()
            if total_h > 0.95:  # keep sub-stochastic
                row_hazard *= 0.95 / total_h

            moved = pop[s, i] * row_hazard
            flow[s, i, :] += moved
            pop[s, i] -= moved.sum()
            pop[s, :] += moved  # moved[i] == 0 by construction (no i->i term)

    # ---- S4 inflow tap (Modern only) ----
    inflow = mech.s4_inflow(t, p.s4_N0, p.s4_g_annual, modern_vis_total, p.s4_gamma)
    modern_vis_slice = vis[MODERN_BRANDS]
    modern_shares = modern_vis_slice / max(modern_vis_slice.sum(), 1e-9)
    for k, b in enumerate(MODERN_BRANDS):
        pop[SI["S4_NEW"], b] += inflow * modern_shares[k]
    cum_inflow = state.cum_inflow + inflow

    # ---- ratchet update (cumulative, then re-derive) ----
    cum_flow = state.cum_flow + flow
    ratchet = mech.update_ratchet(cum_flow, p.pop0.sum(axis=1), p.ratchet_scale)

    # ---- decline index D(t) ----
    legacy_now = float(pop[:, LEGACY_BRANDS].sum())
    D = 1.0 - (legacy_now / state.legacy0)

    # ---- contract participation / defection at reset windows ----
    contract_held = state.contract_held.copy()
    if t % 12 == p.reset_month_mod:
        for c in range(N_CHANNELS):
            if contract_held[c]:
                p_defect = mech.defect_probability(O_c[c], granite_pay[c], p.sigma_bluff_frac)
                defect = (rng.uniform() < p_defect) if rng is not None else (granite_pay[c] < O_c[c])
                if defect:
                    contract_held[c] = False
            else:
                if granite_pay[c] >= (1.0 + p.reversal_premium) * O_c[c]:
                    contract_held[c] = True

    # ---- cash / NPV ----
    unit_cost = p.unit_cost_pct * p.P_list0
    volume = pop.sum(axis=0)  # [B]
    cash = dict(state.cash)
    disc = (1.0 + p.discount_rate_annual) ** (t / 12.0)
    for house in HOUSES:
        brands_h = [b for b in REAL_BRANDS if HOUSE_OF_BRAND[b] == house]
        gross = sum((P_net[b] - unit_cost[b]) * volume[b] for b in brands_h)
        trade_spend = float(trade_bid[brands_h, :].sum())
        cash[house] += (gross - trade_spend) / disc

    return MarketState(
        t=t + 1,
        pop=pop,
        cum_flow=cum_flow,
        ratchet=ratchet,
        P_list=P_list,
        promo_subsidy=promo,
        contract_held=contract_held,
        D=D,
        legacy0=state.legacy0,
        cash=cash,
        cum_inflow=cum_inflow,
    )


# ============================================================================
# 6. RUN
# ============================================================================

def run(p: Params, levers_fn: Optional[Callable] = None, months: Optional[int] = None,
        seed: Optional[int] = None) -> dict:
    """
    Executes the sim.
    seed=None -> deterministic mode (threshold-rule defection: W < O defects).
    seed=int  -> stochastic mode (drawn defection against P(defect)), for the
                 Monte Carlo cascade / B* sweeps in Sunday's sweep.py.
    Returns a dict of time-indexed arrays (a lightweight "History").
    """
    months = months or p.months
    levers_fn = levers_fn or default_levers_fn()
    rng = np.random.default_rng(seed) if seed is not None else None

    state = init_state(p)
    hist = {"t": [], "pop": [], "D": [], "contract_held": [], "P_net": [],
            "cash": [], "O_c": [], "granite_pay": [], "trade_bid": []}

    for t in range(months):
        levers = levers_fn(state, p, t)
        hist["t"].append(t)
        hist["pop"].append(state.pop.copy())
        hist["D"].append(state.D)
        hist["contract_held"].append(state.contract_held.copy())
        hist["P_net"].append((levers["P_list"] - levers["promo_subsidy"]).copy())
        hist["cash"].append(dict(state.cash))
        hist["O_c"].append(levers["O_c"].copy())
        hist["granite_pay"].append(levers["granite_pay"].copy())
        hist["trade_bid"].append(levers["trade_bid"].copy())

        state = step(state, p, levers, t, rng)

    hist["pop"] = np.array(hist["pop"])                       # [T, S, B]
    hist["D"] = np.array(hist["D"])                            # [T]
    hist["contract_held"] = np.array(hist["contract_held"])    # [T, C]
    hist["P_net"] = np.array(hist["P_net"])                    # [T, B]
    hist["O_c"] = np.array(hist["O_c"])                        # [T, C]
    hist["granite_pay"] = np.array(hist["granite_pay"])        # [T, C]
    hist["trade_bid"] = np.array(hist["trade_bid"])            # [T, B, C]
    hist["final_state"] = state
    return hist


# ============================================================================
# 7. ANALYSIS HELPERS
# ============================================================================

def legacy_total(hist):
    return hist["pop"][:, :, LEGACY_BRANDS].sum(axis=(1, 2))


def modern_total(hist):
    return hist["pop"][:, :, MODERN_BRANDS].sum(axis=(1, 2))


def brand_total(hist, brand_idx):
    return hist["pop"][:, :, brand_idx].sum(axis=1)


def cagr(series, months):
    if series[0] <= 0:
        return float("nan")
    years = months / 12.0
    return (series[-1] / series[0]) ** (1.0 / years) - 1.0


def first_defection_month(hist):
    held = hist["contract_held"]
    defected_any = ~held.all(axis=1)
    if not defected_any.any():
        return None
    return int(np.argmax(defected_any))
