"""BREAKPOINT shared UI components (spec sections 9, 12, 14)."""

from __future__ import annotations
import base64
from pathlib import Path
import streamlit as st

ASSETS = Path(__file__).resolve().parent.parent / "assets"
STYLES = Path(__file__).resolve().parent.parent / "styles"

C = {
    "carbon": "#111820", "slate": "#202B35", "steel": "#18222B", "mist": "#E6E7E8",
    "muted": "#83919C", "gunmetal": "#34414C", "amber": "#FFB000", "teal": "#3FA7A0",
    "red": "#D94B4B", "green": "#77B89B",
}

# state -> (css class, label)
STATES = {
    "HELD": ("bp-held", "HELD"),
    "PRESSURE": ("bp-pressure", "PRESSURE"),
    "WALKAWAY RISK": ("bp-walkaway", "WALKAWAY RISK"),
    "BREAKPOINT": ("bp-breakpoint", "BREAKPOINT"),
}


def load_theme():
    """Inject the stylesheet + embedded fonts once per session."""
    css = (STYLES / "breakpoint.css").read_text()
    fonts = ("@import url('https://fonts.googleapis.com/css2?"
             "family=IBM+Plex+Serif:wght@500;600&family=Inter:wght@400;500;600&"
             "family=IBM+Plex+Mono:wght@400;500&display=swap');")
    st.markdown(f"<style>{fonts}\n{css}</style>", unsafe_allow_html=True)


def _asset_uri(name: str) -> str:
    """Data-URI for an asset. Handles both SVG (text) and PNG (binary)."""
    path = ASSETS / name
    if name.endswith(".svg"):
        raw = path.read_text().encode()
        return "data:image/svg+xml;base64," + base64.b64encode(raw).decode()
    raw = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def brand_header(subtitle: str | None = None):
    """Full brand lockup (phone mark + BREAKPOINT + DECISION SIMULATION)."""
    uri = _asset_uri("breakpoint-lockup-dark.png")
    st.markdown(
        f'<div style="display:flex;align-items:center;margin:2px 0 2px 0">'
        f'<img src="{uri}" height="82" alt="Breakpoint — Decision Simulation"/></div>',
        unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="bp-card-sub" style="margin:2px 0 10px 0">{subtitle}</div>',
                    unsafe_allow_html=True)


def sidebar_brand():
    uri = _asset_uri("breakpoint-mark.png")
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;padding:2px 0 12px 0">'
        f'<img src="{uri}" height="42"/>'
        f'<span style="font-family:\'IBM Plex Serif\',serif;font-weight:600;'
        f'letter-spacing:2px;color:{C["mist"]};font-size:1.05rem">BREAKPOINT</span></div>',
        unsafe_allow_html=True)


def eyebrow(text: str):
    st.markdown(f'<div class="bp-eyebrow">{text}</div>', unsafe_allow_html=True)


def card(label, value, sub=None, color=None):
    color = color or C["mist"]
    st.markdown(
        f'<div class="bp-card"><div class="bp-card-label">{label}</div>'
        f'<div class="bp-card-value" style="color:{color}">{value}</div>'
        f'{f"<div class=\'bp-card-sub\'>{sub}</div>" if sub else ""}</div>',
        unsafe_allow_html=True)


def hero_card(label, value, sub=None, color=None):
    color = color or C["amber"]
    st.markdown(
        f'<div class="bp-hero"><div class="bp-card-label">{label}</div>'
        f'<div class="bp-hero-value" style="color:{color}">{value}</div>'
        f'{f"<div class=\'bp-card-sub\'>{sub}</div>" if sub else ""}</div>',
        unsafe_allow_html=True)


def story_strip(cells):
    """The three-beat story strip: ROI says cut / history says careful / the
    model's answer. `cells` is [(step, headline, body, variant)] where variant
    is one of tension | caution | answer."""
    inner = "".join(
        f'<div class="bp-story-cell is-{variant}">'
        f'<div class="bp-story-step">{step}</div>'
        f'<div class="bp-story-head">{head}</div>'
        f'<div class="bp-story-body">{body}</div></div>'
        for step, head, body, variant in cells)
    st.markdown(f'<div class="bp-story">{inner}</div>', unsafe_allow_html=True)


def job_lines(jobs):
    """The four jobs the spend does. `jobs` is [(title, body, is_cuttable)]."""
    inner = "".join(
        f'<div class="bp-job{" is-cuttable" if cuttable else ""}">'
        f'<div class="bp-job-n">{i}</div>'
        f'<div class="bp-job-t"><b>{title}</b> — {body}</div></div>'
        for i, (title, body, cuttable) in enumerate(jobs, 1))
    st.markdown(f'<div>{inner}</div>', unsafe_allow_html=True)


def badge(state: str):
    cls, lbl = STATES.get(state, ("bp-held", state))
    return f'<span class="bp-badge {cls}">{lbl}</span>'


def status_badge(state: str):
    st.markdown(badge(state), unsafe_allow_html=True)


def warning(title: str, body: str):
    st.markdown(
        f'<div class="bp-warn"><div class="bp-warn-title">{title}</div>'
        f'<div>{body}</div></div>', unsafe_allow_html=True)


def money(x, unit="MM", prefix="$", digits=1):
    return f"{prefix}{x:,.{digits}f}{unit}"
