"""BREAKPOINT Plotly theme (spec section 10 chart rules)."""

CARBON = "#111820"
SLATE = "#202B35"
STEEL = "#18222B"
MIST = "#E6E7E8"
MUTED = "#83919C"
GUNMETAL = "#34414C"
AMBER = "#FFB000"
TEAL = "#3FA7A0"
RED = "#D94B4B"
GREEN = "#77B89B"

# Brand -> color, restrained; the modern leader carries amber signal.
BRAND_COLORS = {
    "GRANITE_SELECT": "#6E8CA0", "BOWERS": "#4B6270",
    "GRANITE_ONE": TEAL, "BOWER_FRESH": "#2C6E6A", "NORD": AMBER,
}


def style(fig, height=360, title=None, ytitle=None, xtitle=None):
    """Apply the Breakpoint chart language to a Plotly figure.
    Serif title sits above the plot (not inside); dark field; hairline grid."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=SLATE, plot_bgcolor=SLATE,
        font=dict(color=MIST, family="Inter", size=12),
        height=height,
        margin=dict(l=54, r=22, t=44 if title else 16, b=42),
        title=dict(text=title, font=dict(family="IBM Plex Serif, Georgia, serif",
                                         size=15, color=MIST), x=0.0, xanchor="left") if title else None,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=MUTED),
                    orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0),
        hoverlabel=dict(bgcolor=STEEL, font=dict(family="IBM Plex Mono", color=MIST)),
    )
    fig.update_xaxes(gridcolor=GUNMETAL, zerolinecolor=GUNMETAL, linecolor=GUNMETAL,
                     title=dict(text=xtitle, font=dict(size=11, color=MUTED)) if xtitle else None,
                     tickfont=dict(family="IBM Plex Mono", size=10, color=MUTED))
    fig.update_yaxes(gridcolor=GUNMETAL, zerolinecolor=GUNMETAL, linecolor=GUNMETAL,
                     title=dict(text=ytitle, font=dict(size=11, color=MUTED)) if ytitle else None,
                     tickfont=dict(family="IBM Plex Mono", size=10, color=MUTED))
    return fig
