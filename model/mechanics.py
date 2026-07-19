"""
TOLLGATE v1.0 -- Mechanics
Pure functions implementing the hazard/contest/participation math from
build spec (tollgate_spec_v1.md) section 3. Everything is vectorized NumPy;
no Python-level loops over individual consumers.

Zero external dependencies beyond numpy + stdlib math, so the app deploys
clean on Streamlit Cloud / Railway without a scipy pin. normal_cdf/normal_ppf
below replace scipy.stats.norm for this purpose.
"""

from __future__ import annotations
import math
import numpy as np


# ----------------------------------------------------------------------------
# Normal distribution helpers (stdlib-only, no scipy dependency)
# ----------------------------------------------------------------------------

def normal_cdf(x):
    """Standard normal CDF, vectorized, via math.erf."""
    x = np.asarray(x, dtype=float)
    erf_vec = np.vectorize(math.erf)
    return 0.5 * (1.0 + erf_vec(x / math.sqrt(2.0)))


def normal_ppf(p):
    """
    Inverse standard normal CDF (quantile function).
    Acklam's rational approximation (~1.15e-9 max abs error). Scalar or array.
    """
    p = np.asarray(p, dtype=float)
    scalar_input = (p.ndim == 0)
    p = np.atleast_1d(p).astype(float)

    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]

    p_low = 0.02425
    out = np.empty_like(p)

    lo = p < p_low
    hi = p > (1 - p_low)
    mid = ~lo & ~hi

    if np.any(lo):
        q = np.sqrt(-2 * np.log(p[lo]))
        out[lo] = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                  ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

    if np.any(hi):
        q = np.sqrt(-2 * np.log(1 - p[hi]))
        out[hi] = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

    if np.any(mid):
        q = p[mid] - 0.5
        r = q * q
        out[mid] = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
                   (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

    return float(out[0]) if scalar_input else out


# ----------------------------------------------------------------------------
# spec 3.1 -- Gap migration hazard: the S-curve with a ratchet
# ----------------------------------------------------------------------------

def gap_migration_hazard(G, theta, beta, h0, ratchet_reverse, kappa, vis_j, gamma):
    """
    Monthly hazard of migrating i -> j for one segment.

        h_ij = h0 * sigmoid( beta * (G - theta - kappa*theta*ratchet_reverse) ) * vis_j**gamma

    G                net price gap P_net_i - P_net_j ($). Positive = i pricier than j.
    theta            segment migration threshold ($)
    beta             knee steepness (per $)
    h0               peacetime hazard ceiling (fraction/month)
    ratchet_reverse  ratchet[s, j, i] in caller's state -- i.e. the DESTINATION-then
                     -ORIGIN pair, representing "segment s previously flowed j->i".
                     A prior flow in the opposite direction penalizes *this* flow
                     (i->j) since it would be a reversal/recapture. 0 = no prior
                     reversal to fight, 1 = fully ratcheted. Caller is responsible
                     for passing the swapped-index lookup; see engine.step().
    kappa            ratchet premium multiplier on theta
    vis_j            destination brand's aggregate visibility share [0,1]
    gamma            visibility gate exponent
    All args broadcast via numpy; scalars or arrays.
    """
    arg = beta * (G - theta - kappa * theta * ratchet_reverse)
    sig = 1.0 / (1.0 + np.exp(-arg))
    return h0 * sig * np.power(np.clip(vis_j, 1e-6, 1.0), gamma)


# ----------------------------------------------------------------------------
# spec 3.2 -- Category exit & S4 inflow
# ----------------------------------------------------------------------------

def exit_hazard(net_price_index, base_index, eta, e0, a):
    """h_exit = e0 * (NetPriceIndex/BaseIndex)^eta + a   (a = aging/baseline attrition)"""
    ratio = np.asarray(net_price_index, dtype=float) / base_index
    return e0 * np.power(np.clip(ratio, 1e-6, None), eta) + a


def s4_inflow(t_months, N0, g_N_annual, modern_visibility_total, gamma_N):
    """New-to-category entrants this month; drawn in only via the Modern format."""
    monthly_growth = (1.0 + g_N_annual) ** (1.0 / 12.0)
    return N0 * (monthly_growth ** t_months) * np.power(
        np.clip(modern_visibility_total, 1e-6, 1.0), gamma_N
    )


# ----------------------------------------------------------------------------
# spec 3.3 -- Visibility contest (Tullock) + contract override
# ----------------------------------------------------------------------------

def tullock_shares(bids, rho: float = 1.0):
    """
    bids: array of non-negative $ bids (last axis = competitors).
    Returns visibility shares summing to 1 along the last axis.
    All-zero-bid edge case splits evenly rather than dividing by zero.
    """
    bids = np.clip(np.asarray(bids, dtype=float), 0.0, None)
    w = np.power(bids + 1e-9, rho)
    total = w.sum(axis=-1, keepdims=True)
    return w / total


def legacy_visibility(bid_select, bid_bowers, contract_held: bool, v_floor: float):
    """
    Two-brand Tullock contest for the Legacy slot in one channel.
    While Granite holds the channel's contract, GRANITE_SELECT's share is
    pinned at v_floor regardless of the raw bid ratio (spec 3.3 contract
    override); BOWERS takes the residual. Once defected, pure Tullock.
    """
    if contract_held:
        return np.array([v_floor, 1.0 - v_floor])
    return tullock_shares(np.array([bid_select, bid_bowers]))


def modern_visibility(bid_one, bid_fresh, bid_nord, legacy_contract_held: bool, rival_cap: float):
    """
    Three-brand Tullock contest for the Modern slot in one channel.
    While Granite's LEGACY contract is held in this channel, rival modern
    bids (Bower Fresh, NORD) are capped at rival_cap x their raw bid -- the
    crowded-shelf effect that lets a contract defection "release" NORD's
    visibility (spec 3.5 cascade mechanic).
    """
    mult = rival_cap if legacy_contract_held else 1.0
    return tullock_shares(np.array([bid_one, bid_fresh * mult, bid_nord * mult]))


# ----------------------------------------------------------------------------
# spec 3.4 -- Retailer participation: the chicken game
# ----------------------------------------------------------------------------

def outside_option(best_competing_offer, delta_c, D_t, s_c):
    """O_c(t) = BestCompetingOffer_c(t) + delta_c * D(t) - s_c"""
    return best_competing_offer + delta_c * D_t - s_c


def defect_probability(O_c, W_c, sigma_bluff_frac):
    """P(defect) = Phi((O_c - W_c) / sigma_bluff),  sigma_bluff = frac * O_c."""
    sigma = np.clip(sigma_bluff_frac * np.clip(O_c, 1e-6, None), 1e-6, None)
    return normal_cdf((O_c - W_c) / sigma)


def min_viable_payment(O_c, sigma_bluff_frac, alpha):
    """
    W*_c(t) = O_c + z_(1-alpha) * sigma_bluff -- the payment that holds
    defection probability at exactly `alpha`. Paying at the (1-alpha)
    quantile above O_c caps P(defect) at alpha by construction:
    defect_probability(O_c, W*, frac) == alpha.
    """
    O_c = np.asarray(O_c, dtype=float)
    sigma = sigma_bluff_frac * np.clip(O_c, 1e-6, None)
    z = normal_ppf(1.0 - alpha)
    return O_c + z * sigma


# ----------------------------------------------------------------------------
# spec 3.1 -- hysteresis bookkeeping
# ----------------------------------------------------------------------------

def update_ratchet(cum_flow_mass, init_mass_by_segment, scale: float = 0.02):
    """
    ratchet[s,i,j] climbs toward 1 as CUMULATIVE i->j flow mass accumulates,
    relative to a small fraction (`scale`) of segment s's starting mass.
    Pure function of cumulative state -- caller (engine.MarketState) owns
    the running total and re-derives ratchet from it each step.

    cum_flow_mass: array [S, N_BRANDS, N_BRANDS], cumulative mass ever moved i->j.
    init_mass_by_segment: array [S], each segment's t=0 total population.
    """
    denom = np.clip(np.asarray(init_mass_by_segment, dtype=float), 1e-6, None)[:, None, None] * scale
    return 1.0 - np.exp(-cum_flow_mass / denom)
