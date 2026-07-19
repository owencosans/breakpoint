"""BREAKPOINT — Decision (landing). Answers four questions in 15 seconds:
what cut, how much headroom, who's closest to walking, what if we overshoot."""

import sys
from pathlib import Path
import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
for sub in ("components", "styles", "model"):
    p = str(_ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import ui, charts, decision as dec  # noqa: E402
from sidebar import control_rail    # noqa: E402

ui.load_theme()
P = control_rail()

ui.brand_header("Find the cut that changes everything.")

cut = dec.cutline(P["scenario"], P["war_chest"], P["alpha"], P["months"])
board = dec.retailer_board(P["scenario"], P["divest"], P["war_chest"], P["alpha"], P["months"])
state = dec.overall_state(board, cut, P["divest"])
closest = board[0]

cutline_pct = cut["cutline_pct"] * 100
bpt_pct = cut["breakpoint_pct"] * 100
proposed_pct = P["divest"] * 100

# The rail sits at 0% in the baseline scenario, so only name the proposal as
# "the ask" once it actually is one. Otherwise the strip reads "finance wants 0%".
if proposed_pct > cutline_pct:
    ask = (f"Measured promo and dealer-payment ROI looks poor — a dollar of spend visibly "
           f"buys less than a dollar of lift. The proposal on the rail is a {proposed_pct:.0f}% cut.")
else:
    ask = ("Measured promo and dealer-payment ROI looks poor — a dollar of spend visibly buys "
           "less than a dollar of lift. Finance wants deep cuts, and on paper it is right.")

# ---- the three-beat story, up front, before any number needs explaining ----
ui.story_strip([
    ("Step 1", "ROI says cut", ask, "tension"),
    ("Step 2", "History says careful",
     "The data is calm because we have been paying to keep it calm. Customers "
     "and dealers lost past the threshold do not come back.", "caution"),
    ("Step 3", f"The model says {cutline_pct:.0f}%, not {bpt_pct:.0f}%",
     f"Cut to {cutline_pct:.0f}% and you recover real waste. Cut to {bpt_pct:.0f}% "
     f"and a dealer walks.", "answer"),
])

with st.expander("Why the ROI number is deceiving here"):
    st.markdown("The spend is not buying lift. It is doing four jobs ROI cannot see.")
    ui.job_lines([
        ("Price discrimination",
         "targeted offers reach the twitchy customers without repricing the loyal "
         "base — a base rate for the book that renews, underwritten offers for the "
         "lapse risks.", False),
        ("Retention against one-way doors",
         "customers who down-trade or defect mostly never return, and winback costs "
         "a multiple of retention. This spend prevents rare, permanent losses.", False),
        ("Renting the shelf",
         "dealer payments buy placement and buy the dealer <i>not</i> taking a "
         "rival's money. The dealer runs its own P&amp;L and is always comparing.", False),
        ("The standoff tax",
         "some of it genuinely is competitive deadweight. This is the part that is "
         "safely cuttable — which is why the answer is never simply spend or don't.", True),
    ])
    st.markdown(
        '<div class="bp-card" style="border-left:3px solid '
        f'{ui.C["amber"]};margin-top:10px">'
        "Measured price-sensitivity reads low <i>because</i> the gap was managed below "
        "the danger line in every year of the data. The regression only ever saw the "
        "years the levee held — low measured sensitivity is evidence the spend is "
        "working, not evidence it is wasted.</div>",
        unsafe_allow_html=True)

    jobs = dec.spend_jobs(P["scenario"], P["war_chest"], P["alpha"], P["months"])
    st.plotly_chart(charts.four_jobs_bar(jobs["components"]), width="stretch")
    st.caption("Illustrative decomposition. The first three bars are load-bearing — cutting "
               "them opens a door. The fourth, competitive offset, is the standoff tax: "
               "the part that is safely cuttable.")

ui.eyebrow("Decision")
st.markdown("#### How far can finance cut before the sales team is right?")

closest_name = dec.RETAILER_SHORT[closest["retailer"]]

# ---- hero row: the dominant output ----
h1, h2, h3 = st.columns([2, 2, 2])
with h1:
    ui.hero_card("Cut to here (Cutline)", f"{cutline_pct:.0f}%",
                 f"recovers {ui.money(cut['recoverable'])} of genuine waste, "
                 f"every dealer still held")
with h2:
    ui.card("Room for error", f"{cut['headroom_pct']*100:.0f}%",
            f"the gap between the Cutline and the Breakpoint at {bpt_pct:.0f}%",
            ui.C["amber"])
with h3:
    col = {"HELD": ui.C["teal"], "PRESSURE": ui.C["amber"],
           "WALKAWAY RISK": ui.C["amber"], "BREAKPOINT": ui.C["red"]}[state]
    ui.card("Where the proposal lands", state,
            f"at the {proposed_pct:.0f}% cut on the control rail", col)

# ---- the decision band ----
st.plotly_chart(charts.decision_band(cut, P["divest"]), width="stretch")

# ---- four-question strip ----
q1, q2, q3, q4 = st.columns(4)
with q1:
    ui.card("What cut is recommended?", f"{cutline_pct:.0f}%",
            "the Cutline — recovering the standoff tax, nothing load-bearing",
            ui.C["teal"])
with q2:
    ui.card("What it recovers", ui.money(cut["recoverable"]),
            "real savings, no door opened", ui.C["green"])
with q3:
    cs_state = closest["state"]
    cs_col = {"HELD": ui.C["teal"], "PRESSURE": ui.C["amber"],
              "WALKAWAY RISK": ui.C["amber"], "BREAKPOINT": ui.C["red"]}[cs_state]
    ui.card("Who walks first", closest_name,
            f"{closest['distance']:.2f}× switching-cost buffer left — "
            f"{dec.RETAILER_MECHANISM[closest['retailer']]}", cs_col)
with q4:
    ui.card("If you overshoot", f"{bpt_pct:.0f}%+",
            f"cut past this → {closest_name}'s math flips → the shelf opens to NORD, "
            f"and winback costs a multiple of what holding cost", ui.C["red"])

# ---- consequence line ----
if state == "BREAKPOINT":
    ui.warning("Breakpoint crossed",
               f"At a {proposed_pct:.0f}% cut, {closest_name} is now economically better off "
               f"leaving. That door does not reopen on the way back — winback costs a multiple "
               f"of what holding cost, and the released shelf is a rival's to fill. "
               f"Pull back below {bpt_pct:.0f}%.")
elif state in ("PRESSURE", "WALKAWAY RISK"):
    # Pressure has two distinct causes: a cut past the Cutline, or a dealer whose
    # own economics are already tight regardless of how little we have cut. Saying
    # "your 0% cut is past the Cutline" when it plainly is not destroys trust.
    if proposed_pct > cutline_pct:
        body = (f'The {proposed_pct:.0f}% cut is past the Cutline ({cutline_pct:.0f}%) but still '
                f'short of the Breakpoint ({bpt_pct:.0f}%). From here every further point of cut '
                f'buys less saving and more risk — and {closest_name} is the one nearest its '
                f'walkaway point.')
    else:
        body = (f'The proposed cut is inside the Cutline ({cutline_pct:.0f}%), but the pressure is '
                f'not coming from the cut — {closest_name} is already close to its walkaway point '
                f'on the current dealer economics, with {closest["distance"]:.2f}× of switching-cost '
                f'buffer left. Cutting toward the Breakpoint ({bpt_pct:.0f}%) spends that buffer.')
    st.markdown(
        f'<div class="bp-card" style="border-left:3px solid {ui.C["amber"]}">{body}</div>',
        unsafe_allow_html=True)
else:
    st.markdown(
        f'<div class="bp-card" style="border-left:3px solid {ui.C["teal"]}">'
        f'Every dealer held. The recommended cut recovers {ui.money(cut["recoverable"])} without '
        f'moving anyone toward the exit, and {cut["headroom_pct"]*100:.0f} points of room remain '
        f'before the Breakpoint.</div>',
        unsafe_allow_html=True)

st.caption("Cutline = cut this far and you are recovering genuine waste. Breakpoint = cut this "
           "far and a dealer rationally walks, rivals take the released shelf, and the loss is "
           "partly irreversible. The space between the two is your margin for error.")
