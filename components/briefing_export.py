"""BREAKPOINT — one-page executive briefing export (spec section 13).
Renders a light-background, print-ready HTML document (not a screenshot of the
dark dashboard). The user prints to PDF from the browser."""

from __future__ import annotations
import base64
from datetime import date
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / "assets"


def _wordmark_uri():
    raw = (_ASSETS / "breakpoint-lockup-dark.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def build_briefing_html(P, cut, board, state, entry, money_fmt, baseline_cut=None) -> str:
    """baseline_cut: the peacetime cutline dict, passed only when the scenario
    runs a rival surge — used to caveat the inflated savings figure."""
    closest = board[0]
    scenario = P["scenario"]
    today = date.today().isoformat()

    # Under a surge the recovered-savings figure inflates while total cash
    # falls. The one-pager travels without a narrator, so the caveat must too.
    surge_note = ""
    if baseline_cut is not None:
        drop = baseline_cut["npv_at_cutline"] - cut["npv_at_cutline"]
        if drop > 0.02 * abs(baseline_cut["npv_at_cutline"]):
            surge_note = (f" Note: under the rival surge this savings figure is larger because "
                          f"defense costs more, not because the outlook improved — total cash at "
                          f"the Cutline sits {money_fmt(drop)} below peacetime.")

    state_color = {"HELD": "#2b8a7f", "PRESSURE": "#b9791f",
                   "WALKAWAY RISK": "#b9791f", "BREAKPOINT": "#c0392b"}[state]

    rows = "".join(
        f"<tr><td>{r['label']}</td><td class='num'>{r['stay']:.1f}</td>"
        f"<td class='num'>{r['defect']:.1f}</td><td class='num'>{r['distance']:+.2f}</td>"
        f"<td class='num'>{r['rival_offer_required']:.1f}</td>"
        f"<td><span class='state' style='color:{_state_c(r['state'])}'>{r['state']}</span></td></tr>"
        for r in board)

    # Every posture line opens on the tension: measured ROI argues one way, the
    # model's boundaries argue another. That is the whole brief in one sentence.
    tension = (f"Measured ROI argues for deep cuts; the model recommends "
               f"{cut['cutline_pct']*100:.0f}% and identifies "
               f"{cut['breakpoint_pct']*100:.0f}% as the point where a dealer walks.")

    if state == "BREAKPOINT":
        posture = (f"{tension} At the proposed {P['divest']*100:.0f}% cut, {closest['label']} is "
                   f"already better off leaving, and that loss is only partly reversible. "
                   f"Pull back below {cut['breakpoint_pct']*100:.0f}%.")
    elif state in ("PRESSURE", "WALKAWAY RISK"):
        # Pressure can come from the cut depth or from a dealer that is already
        # tight; do not tell the reader a 0% cut is past the Cutline.
        if P["divest"] > cut["cutline_pct"]:
            posture = (f"{tension} The proposed {P['divest']*100:.0f}% cut sits past the Cutline "
                       f"but short of the Breakpoint: from here each further point buys less "
                       f"saving and more risk.")
        else:
            posture = (f"{tension} The proposed cut is inside the Cutline, but {closest['label']} "
                       f"is already near its walkaway point on current dealer economics — the "
                       f"buffer is {closest['distance']:+.2f}× its switching cost.")
    else:
        posture = (f"{tension} The recommended cut recovers {money_fmt(cut['recoverable'])} "
                   f"while preserving every current dealer relationship.")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Breakpoint Assessment — {scenario}</title>
<style>
  /* Margins and type are tuned so the whole brief lands on ONE printed page:
     16mm margins leave ~673px of printable width and ~1001px of height at
     96dpi. If you add a section, re-measure — do not let it run to page two. */
  @page {{ margin: 16mm; }}
  body {{ font-family: 'Inter','Segoe UI',sans-serif; color:#1b232b; background:#fff;
          font-size: 11px; line-height: 1.38; max-width: 673px; margin: 0 auto; }}
  .num {{ font-family: 'IBM Plex Mono',monospace; text-align:right; }}
  h1 {{ font-family:'IBM Plex Serif',Georgia,serif; font-size:20px; margin:4px 0 0; }}
  h2 {{ font-family:'IBM Plex Serif',Georgia,serif; font-size:13px; margin:10px 0 3px;
        border-bottom:1px solid #d3dae0; padding-bottom:2px; }}
  p {{ margin:3px 0; }}
  /* the four jobs — compact enough that section 2 does not cost a page */
  ol.jobs {{ margin:3px 0 5px 18px; padding:0; }}
  ol.jobs li {{ margin-bottom:1px; }}
  .sub {{ color:#5c6a76; font-size:12px; }}
  .head {{ display:flex; justify-content:space-between; align-items:center;
           background:#111820; border-radius:8px; padding:10px 14px; margin-bottom:4px; }}
  .head h1 {{ color:#E6E7E8; }} .head .sub {{ color:#9aa7b2; }}
  .metrics {{ display:flex; gap:14px; margin:8px 0; }}
  .metric {{ flex:1; border:1px solid #d3dae0; border-radius:6px; padding:7px 10px; }}
  .metric .v {{ font-family:'IBM Plex Mono',monospace; font-size:18px; }}
  .metric .l {{ color:#5c6a76; font-size:10px; text-transform:uppercase; letter-spacing:0.06em; }}
  table {{ width:100%; border-collapse:collapse; margin-top:6px; }}
  th,td {{ text-align:left; padding:4px 8px; border-bottom:1px solid #e2e7ec; font-size:10px; }}
  th {{ color:#5c6a76; text-transform:uppercase; font-size:9px; letter-spacing:0.05em; }}
  .state {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:9px; }}
  .posture {{ border-left:3px solid {state_color}; padding:6px 10px; background:#f7f9fa;
              margin:6px 0; }}
  footer {{ margin-top:14px; color:#8894a0; font-size:9px;
            border-top:1px solid #d3dae0; padding-top:6px; }}
</style></head><body>
  <div class="head">
    <div><img src="{_wordmark_uri()}" height="30"/>
      <h1>Breakpoint Assessment</h1>
      <div class="sub">Recommended investment posture and downside boundaries</div></div>
    <div class="sub" style="text-align:right">Scenario: <b>{scenario}</b><br>{today}</div>
  </div>

  <div class="metrics">
    <div class="metric"><div class="l">Recommended cut</div>
      <div class="v">{cut['cutline_pct']*100:.0f}%</div></div>
    <div class="metric"><div class="l">Savings recovered</div>
      <div class="v">{money_fmt(cut['recoverable'])}</div></div>
    <div class="metric"><div class="l">Headroom to breakpoint</div>
      <div class="v">{cut['headroom_pct']*100:.0f}%</div></div>
    <div class="metric"><div class="l">Posture</div>
      <div class="v" style="color:{state_color}">{state}</div></div>
  </div>

  <h2>1 · Decision</h2>
  <div class="posture">{posture}</div>

  <h2>2 · Why the ROI number is deceiving</h2>
  <p>The spend is not buying lift. It is doing four jobs short-term ROI cannot see:</p>
  <ol class="jobs">
    <li><b>Price discrimination</b> — targeted offers reach the twitchy customers without
        repricing the loyal base.</li>
    <li><b>Retention against one-way doors</b> — customers who defect mostly never return, and
        winback costs a multiple of retention.</li>
    <li><b>Renting the shelf</b> — dealer payments buy placement, and buy the dealer not taking
        a rival's money.</li>
    <li><b>The standoff tax</b> — genuine competitive deadweight, and the only part safely
        cuttable. Recovering it is what the Cutline does.</li>
  </ol>
  <p>Measured price-sensitivity reads low <i>because</i> the gap was managed below the danger
     line in every year of the data — the calm is an artifact of the spend, not evidence
     against it.</p>

  <h2>3 · Economic value captured</h2>
  <p>The recommended cut of {cut['cutline_pct']*100:.0f}% recovers
     {money_fmt(cut['recoverable'])} relative to paying full freight, while remaining below the
     Breakpoint at {cut['breakpoint_pct']*100:.0f}%. The margin between the two is the room for
     error before controlled decline becomes collapse.{surge_note}</p>

  <h2>4 · Closest dealer threshold</h2>
  <p><b>{closest['label']}</b> sits closest to walking, with a safety buffer of
     {closest['distance']:+.2f}× its switching cost. A rival offer near
     {closest['rival_offer_required']:.1f} would tip it.</p>

  <h2>5 · Competitive vulnerability</h2>
  <p>Entry Pressure — the rival funding level that tips at least two dealers — is
     {'approximately ' + format(entry['b_star'], '.0f') if entry['ignites'] else 'above ' + format(entry['b_star'], '.0f')}
     (index $/mo). Below this, the channel is stable; above it, defections cascade, and each
     departure improves the next dealer's leave-versus-stay math.</p>

  <h2>6 · Cascade exposure</h2>
  <table><tr><th>Dealer</th><th class="num">Stays</th><th class="num">Leaves</th>
    <th class="num">Buffer</th><th class="num">Rival $ to tip</th><th>State</th></tr>
    {rows}</table>

  <h2>7 · Assumptions and what would change the recommendation</h2>
  <p class="sub">Category demand is price-inelastic; the contract caps dealer margin and rival
     access; losing a dealer accelerates customer loss there; winback costs a premium over
     retention. A rival funding above Entry Pressure, a cut past the Breakpoint, or a faster
     category decline would each pull the closest dealer below its walkaway point and move the
     recommended cut down. Figures are stylized index units calibrated from public benchmarks —
     no client or employer data.</p>

  <footer>Breakpoint · model v1.1 · scenario "{scenario}" · generated {today} ·
    Stylized illustration, not a forecast. No client or employer data.</footer>
</body></html>"""


def _state_c(state):
    return {"HELD": "#2b8a7f", "PRESSURE": "#b9791f",
            "WALKAWAY RISK": "#b9791f", "BREAKPOINT": "#c0392b"}.get(state, "#5c6a76")
