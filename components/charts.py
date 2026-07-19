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
    # zones (stronger fills + labels)
    fig.add_vrect(x0=0, x1=cutline, fillcolor="rgba(50,166,160,0.16)", line_width=0,
                  annotation_text="SAFE", annotation_position="top left",
                  annotation_font=dict(color=th.TEAL, size=10, family="IBM Plex Mono"))
    fig.add_vrect(x0=cutline, x1=bpt, fillcolor="rgba(233,162,59,0.16)", line_width=0,
                  annotation_text="PRESSURE", annotation_position="top",
                  annotation_font=dict(color=th.AMBER, size=10, family="IBM Plex Mono"))
    fig.add_vrect(x0=bpt, x1=grid[-1], fillcolor="rgba(217,75,75,0.18)", line_width=0,
                  annotation_text="BREACH", annotation_position="top right",
                  annotation_font=dict(color=th.RED, size=10, family="IBM Plex Mono"))
    # cash curve
    fig.add_trace(go.Scatter(x=grid, y=npv, line=dict(color=th.MIST, width=3), name="Cash outcome"))
    # cutline + breakpoint
    fig.add_vline(x=cutline, line=dict(color=th.TEAL, width=2),
                  annotation_text="Cutline", annotation_position="top",
                  annotation_font_color=th.TEAL)
    fig.add_vline(x=bpt, line=dict(color=th.RED, width=2, dash="dash"),
                  annotation_text="Breakpoint", annotation_position="top",
                  annotation_font_color=th.RED)
    # proposed marker
    fig.add_trace(go.Scatter(x=[prop], y=[np.interp(prop, grid, npv)], mode="markers",
                             marker=dict(color=th.AMBER, size=15, symbol="diamond"),
                             name="Proposed cut"))
    return th.style(fig, 360, "Cash outcome across the cut — the line holds, then it doesn't",
                    ytitle="Cash outcome (index $MM)", xtitle="Investment reduction (%)")


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
    """Ordered retailer blocks with propagation cue (spec 9.4)."""
    labels = [r["retailer"] for r in board]
    dist = [r["distance"] for r in board]
    colors = []
    for r in board:
        s = r["state"]
        colors.append({"HELD": th.TEAL, "PRESSURE": th.AMBER,
                       "WALKAWAY RISK": th.AMBER, "BREAKPOINT": th.RED}.get(s, th.MUTED))
    fig = go.Figure(go.Bar(x=labels, y=[max(d, 0.02) for d in dist], marker_color=colors,
                           text=[r["state"] for r in board], textposition="outside",
                           textfont=dict(family="IBM Plex Mono", size=11)))
    return th.style(fig, 320, "Order of vulnerability — who flips first, and why the next follows",
                    ytitle="Safety buffer (× switching cost)")


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
    fig = go.Figure(go.Bar(x=list(components.keys()), y=list(components.values()),
                           marker_color=[th.TEAL, th.GREEN, th.AMBER, "#6E8CA0"]))
    return th.style(fig, 300, "What the investment actually buys",
                    ytitle="Value contribution (index $MM)")
