"""BREAKPOINT chart builders (spec sections 9, 10). Each returns a styled fig."""

from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import plotly.graph_objects as go

_STYLES = Path(__file__).resolve().parent.parent / "styles"
if str(_STYLES) not in sys.path:
    sys.path.insert(0, str(_STYLES))
import plotly_theme as th  # noqa: E402


def decision_band(cut_info, proposed_pct):
    """The signature component: a horizontal decision band with stable /
    pressure / breach zones, the recommended Cutline, the Breakpoint, and the
    proposed cut marker."""
    grid = cut_info["grid"] * 100
    npv = cut_info["npv"]
    cutline = cut_info["cutline_pct"] * 100
    bpt = cut_info["breakpoint_pct"] * 100
    prop = proposed_pct * 100

    fig = go.Figure()
    # Zone labels ride along the BOTTOM of the plot; the Cutline/Breakpoint
    # annotations own the top. Separating them vertically is what keeps the two
    # label families from colliding when headroom is narrow.
    zone_font = dict(size=10, family="IBM Plex Mono")
    fig.add_vrect(x0=0, x1=cutline, fillcolor="rgba(50,166,160,0.16)", line_width=0,
                  annotation_text="SAFE", annotation_position="bottom left",
                  annotation_font=dict(color=th.TEAL, **zone_font))
    fig.add_vrect(x0=cutline, x1=bpt, fillcolor="rgba(233,162,59,0.16)", line_width=0,
                  annotation_text="PRESSURE", annotation_position="bottom",
                  annotation_font=dict(color=th.AMBER, **zone_font))
    fig.add_vrect(x0=bpt, x1=grid[-1], fillcolor="rgba(217,75,75,0.18)", line_width=0,
                  annotation_text="BREACH", annotation_position="bottom right",
                  annotation_font=dict(color=th.RED, **zone_font))
    # cash curve
    fig.add_trace(go.Scatter(x=grid, y=npv, line=dict(color=th.MIST, width=3), name="Cash outcome"))
    # Cutline leans left, Breakpoint leans right, so they stay legible even when
    # the headroom between them is only a grid step or two.
    fig.add_vline(x=cutline, line=dict(color=th.TEAL, width=2),
                  annotation_text="Cutline", annotation_position="top left",
                  annotation_font=dict(color=th.TEAL, size=12))
    fig.add_vline(x=bpt, line=dict(color=th.RED, width=2, dash="dash"),
                  annotation_text="Breakpoint", annotation_position="top right",
                  annotation_font=dict(color=th.RED, size=12))
    # Proposed marker, labelled in place. Direct labelling beats a legend here:
    # the top-right legend used to sit on top of the "Breakpoint" annotation.
    fig.add_trace(go.Scatter(x=[prop], y=[np.interp(prop, grid, npv)], mode="markers+text",
                             marker=dict(color=th.AMBER, size=15, symbol="diamond"),
                             text=["Proposed cut"], textposition="bottom center",
                             textfont=dict(color=th.AMBER, size=11, family="IBM Plex Mono"),
                             name="Proposed cut", showlegend=False, cliponaxis=False))
    fig = th.style(fig, 400, "Cash outcome across the cut — the line holds, then it doesn't",
                   ytitle="Cash outcome (index $MM)", xtitle="Investment reduction (%)")
    fig.update_layout(showlegend=False, margin=dict(l=64, r=28, t=52, b=52))
    return fig


def stay_vs_leave(pnl_row_stay, pnl_row_defect, switch_cost, label):
    """Mirrored stay/defect P&L component stacks for one retailer."""
    sc, dc = pnl_row_stay, pnl_row_defect
    cats = ["STAY on contract", "LEAVE"]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Our payment", x=cats, y=[sc["payments_granite"], 0],
                         marker_color=th.AMBER))
    fig.add_trace(go.Bar(name="Our-brand margin", x=cats,
                         y=[sc["margin_granite"], dc["margin_granite"]], marker_color="#6E8CA0"))
    fig.add_trace(go.Bar(name="Rival-brand margin", x=cats,
                         y=[sc["margin_rivals"], dc["margin_rivals"]], marker_color="#4B6270"))
    fig.add_trace(go.Bar(name="Rival money", x=cats,
                         y=[sc["payments_rivals"], dc["payments_rivals"]], marker_color=th.TEAL))
    fig.add_trace(go.Bar(name="Space reallocation", x=cats,
                         y=[0, dc["realloc_gain"]], marker_color=th.GREEN))
    fig.add_trace(go.Bar(name="Switching cost", x=cats, y=[0, -switch_cost], marker_color=th.RED))
    fig.update_layout(barmode="relative")
    return th.style(fig, 380, f"{label} — monthly economics, stay vs. leave",
                    ytitle="$ / month (index)")


def cascade_blocks(board, first_defection):
    """Ordered dealer blocks with propagation cue (spec 9.4).

    Bar height is the cut depth at which each dealer's own math flips — the
    measured quantity the ordering uses. Dealers that never break in the sweep
    are drawn at the top of the range and labelled, rather than dropped."""
    labels = [r["label"].split(" (")[0] for r in board]
    top = 0.8
    depths = [(r["breaks_at"] if r["breaks_at"] is not None else top) * 100 for r in board]
    colors = [{"HELD": th.TEAL, "PRESSURE": th.AMBER,
               "WALKAWAY RISK": th.AMBER, "BREAKPOINT": th.RED}.get(r["state"], th.MUTED)
              for r in board]
    text = [(f"{r['breaks_at']*100:.0f}%" if r["breaks_at"] is not None else "holds")
            for r in board]
    fig = go.Figure(go.Bar(x=labels, y=depths, marker_color=colors,
                           text=text, textposition="outside",
                           textfont=dict(family="IBM Plex Mono", size=11), cliponaxis=False))
    fig = th.style(fig, 320, "Order of vulnerability — who flips first, and why the next follows",
                   ytitle="Cut depth at which this dealer walks (%)")
    fig.update_yaxes(range=[0, top * 100 * 1.15])
    return fig


def phase_diagram(ph, b_star, cur_wc, cur_defense):
    fig = go.Figure(data=go.Heatmap(
        z=ph["field"], x=ph["entrant_grid"], y=ph["incumbent_grid"],
        colorscale=[[0, th.TEAL], [0.5, th.AMBER], [1, th.RED]], zmin=0, zmax=1,
        colorbar=dict(title="cascade<br>prob", tickfont=dict(family="IBM Plex Mono"))))
    fig.add_vline(x=b_star, line=dict(color=th.MIST, dash="dash"),
                  annotation_text="Entry Pressure", annotation_font_color=th.MIST)
    fig.add_trace(go.Scatter(x=[cur_wc], y=[cur_defense], mode="markers",
                             marker=dict(color="white", size=14, symbol="x"), name="you are here"))
    return th.style(fig, 400, "Where the system tips — rival funding vs. our defense",
                    xtitle="Rival funding (index $/mo)", ytitle="Our defense intensity")


def four_jobs_bar(components):
    """The four jobs the spend is doing. The last bar — competitive offset — is
    the standoff tax: the only part that is safely cuttable, so it carries the
    signal colour while the three load-bearing jobs stay recessive."""
    labels = list(components.keys())
    values = list(components.values())
    colors = [th.TEAL, th.GREEN, "#6E8CA0"] + [th.AMBER] * max(len(labels) - 3, 0)
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=colors[:len(labels)],
        text=[f"{v:,.0f}" for v in values], textposition="outside",
        textfont=dict(family="IBM Plex Mono", size=11, color=th.MIST),
        cliponaxis=False))
    fig = th.style(fig, 320, "What the investment actually buys",
                   ytitle="Value contribution (index $MM)")
    fig.update_xaxes(tickfont=dict(family="Inter", size=11, color=th.MIST))
    fig.update_layout(margin=dict(l=64, r=28, t=52, b=56))
    return fig
