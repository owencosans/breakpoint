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


def build_briefing_html(P, cut, board, state, entry, money_fmt) -> str:
    closest = board[0]
    scenario = P["scenario"]
    today = date.today().isoformat()

    state_color = {"HELD": "#2b8a7f", "PRESSURE": "#b9791f",
                   "WALKAWAY RISK": "#b9791f", "BREAKPOINT": "#c0392b"}[state]

    rows = "".join(
        f"<tr><td>{r['label']}</td><td class='num'>{r['stay']:.1f}</td>"
        f"<td class='num'>{r['defect']:.1f}</td><td class='num'>{r['distance']:+.2f}</td>"
        f"<td class='num'>{r['rival_offer_required']:.1f}</td>"
        f"<td><span class='state' style='color:{_state_c(r['state'])}'>{r['state']}</span></td></tr>"
        for r in board)

    if state == "BREAKPOINT":
        posture = (f"At the proposed {P['divest']*100:.0f}% cut, at least one retailer is now "
                   f"better off leaving. Pull back below {cut['breakpoint_pct']*100:.0f}%.")
    elif state in ("PRESSURE", "WALKAWAY RISK"):
        posture = (f"The proposed {P['divest']*100:.0f}% cut sits past the recommended Cutline "
                   f"({cut['cutline_pct']*100:.0f}%) but below the Breakpoint "
                   f"({cut['breakpoint_pct']*100:.0f}%). Further cuts add risk faster than savings.")
    else:
        posture = (f"The recommended {cut['cutline_pct']*100:.0f}% cut recovers "
                   f"{money_fmt(cut['recoverable'])} while preserving every current relationship.")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Breakpoint Assessment — {scenario}</title>
<style>
  @page {{ margin: 22mm; }}
  body {{ font-family: 'Inter','Segoe UI',sans-serif; color:#1b232b; background:#fff;
          font-size: 12px; line-height: 1.45; max-width: 820px; margin: 0 auto; }}
  .num {{ font-family: 'IBM Plex Mono',monospace; text-align:right; }}
  h1 {{ font-family:'IBM Plex Serif',Georgia,serif; font-size:24px; margin:6px 0 0; }}
  h2 {{ font-family:'IBM Plex Serif',Georgia,serif; font-size:15px; margin:20px 0 6px;
        border-bottom:1px solid #d3dae0; padding-bottom:4px; }}
  .sub {{ color:#5c6a76; font-size:12px; }}
  .head {{ display:flex; justify-content:space-between; align-items:center;
           background:#111820; border-radius:8px; padding:14px 18px; margin-bottom:6px; }}
  .head h1 {{ color:#E6E7E8; }} .head .sub {{ color:#9aa7b2; }}
  .metrics {{ display:flex; gap:20px; margin:14px 0; }}
  .metric {{ flex:1; border:1px solid #d3dae0; border-radius:6px; padding:10px 12px; }}
  .metric .v {{ font-family:'IBM Plex Mono',monospace; font-size:22px; }}
  .metric .l {{ color:#5c6a76; font-size:10px; text-transform:uppercase; letter-spacing:0.06em; }}
  table {{ width:100%; border-collapse:collapse; margin-top:6px; }}
  th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid #e2e7ec; font-size:11px; }}
  th {{ color:#5c6a76; text-transform:uppercase; font-size:10px; letter-spacing:0.05em; }}
  .state {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:10px; }}
  .posture {{ border-left:3px solid {state_color}; padding:8px 12px; background:#f7f9fa;
              margin:8px 0; }}
  footer {{ margin-top:26px; color:#8894a0; font-size:10px;
            border-top:1px solid #d3dae0; padding-top:8px; }}
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

  <h2>2 · Economic value captured</h2>
  <p>The recommended cut of {cut['cutline_pct']*100:.0f}% recovers
     {money_fmt(cut['recoverable'])} relative to paying full freight, while remaining below the
     Breakpoint at {cut['breakpoint_pct']*100:.0f}%. The margin between the two is the room for
     error before controlled decline becomes collapse.</p>

  <h2>3 · Closest retailer threshold</h2>
  <p><b>{closest['label']}</b> sits closest to walking, with a safety buffer of
     {closest['distance']:+.2f}× its switching cost. A rival offer near
     {closest['rival_offer_required']:.1f} would tip it.</p>

  <h2>4 · Competitive vulnerability</h2>
  <p>Entry Pressure — the rival funding level that tips at least two retailers — is
     {'approximately ' + format(entry['b_star'], '.0f') if entry['ignites'] else 'above ' + format(entry['b_star'], '.0f')}
     (index $/mo). Below this, the channel is stable; above it, defections cascade.</p>

  <h2>5 · Cascade exposure</h2>
  <table><tr><th>Retailer</th><th class="num">Stays</th><th class="num">Leaves</th>
    <th class="num">Buffer</th><th class="num">Rival $ to tip</th><th>State</th></tr>
    {rows}</table>

  <h2>6 · Key assumptions</h2>
  <p class="sub">Category demand is price-inelastic; the contract caps retailer margin and rival
     access; losing a retailer accelerates customer loss there; winback costs a premium over
     retention. Figures are stylized index units calibrated from public benchmarks — no client
     or employer data.</p>

  <h2>7 · What would change the recommendation</h2>
  <p>A rival bringing funding above the Entry Pressure level, a deeper cut past the Breakpoint,
     or a faster category decline would each pull the closest retailer below its walkaway point
     and move the recommended cut down.</p>

  <footer>Breakpoint · model v1.1 · scenario "{scenario}" · generated {today} ·
    Stylized illustration, not a forecast. No client or employer data.</footer>
</body></html>"""


def _state_c(state):
    return {"HELD": "#2b8a7f", "PRESSURE": "#b9791f",
            "WALKAWAY RISK": "#b9791f", "BREAKPOINT": "#c0392b"}.get(state, "#5c6a76")
