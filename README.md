# Breakpoint

**Find the cut that changes everything.**

A war-room simulator that identifies how far channel investment can fall before
retailers walk, competitors enter, and controlled decline becomes collapse.

Demonstrated with a stylized, fictional wireless-telecom market (dealer
contract plans vs. digital eSIM). The model itself is category-neutral.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Six views in the control rail: **Decision** (landing), **Retailers**,
**Competition**, **Cascade**, **Assumptions**, **Briefing**.

**Warm-up before a demo:** open the app and click through all six views once.
First load of Competition (phase field) and the Cutline sweep takes ~15–30s and
is cached afterward, so the live demo is instant.

## Deploy

- **Streamlit Community Cloud:** push to GitHub, point at `app.py`.
- **Railway:** `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.

## Structure

```
breakpoint/
├── app.py                     # entry point + st.navigation control rail
├── pages/                     # the six views
│   ├── 01_decision.py         # flagship: the recommended cut + boundary, in 15s
│   ├── 02_retailers.py        # walkaway table + stay-vs-leave economics
│   ├── 03_competition.py      # Entry Pressure (B*) + tipping phase field
│   ├── 04_cascade.py          # order of vulnerability + propagation
│   ├── 05_assumptions.py      # plain-English inputs, grouped by business meaning
│   └── 06_briefing.py         # one-page executive export (print to PDF)
├── components/
│   ├── decision.py            # model adapter: Cutline, Walkaway, states — the vocabulary
│   ├── charts.py              # decision band, stay-vs-leave, cascade, phase
│   ├── ui.py                  # theme loader, cards, badges, brand header
│   ├── sidebar.py             # shared control rail
│   └── briefing_export.py     # light-background executive HTML
├── styles/
│   ├── breakpoint.css         # palette + typography + surface overrides
│   └── plotly_theme.py        # chart language
├── model/                     # the tested simulation core (engine/mechanics/…)
│   └── test_engine.py         # 32 tests incl. calibration + structural P&L gate
└── assets/                    # wordmark, mark, favicon, app icon, social preview (SVG/PNG)
```

## The language system

| Term | Meaning |
|---|---|
| **Cutline** | The recommended reduction — captures the savings, stays clear of the cliff. |
| **Breakpoint** | Where a retailer walks on the central case. Controlled decline → collapse. |
| **Walkaway Point** | The payment level at which a retailer is better off leaving. |
| **Entry Pressure** | The rival funding that tips ≥2 retailers into defecting. |
| **Cascade** | One defection changing the economics of the next. |
| States | **HELD · PRESSURE · WALKAWAY RISK · BREAKPOINT** |

## Tests

```bash
cd model && python -m pytest test_engine.py -v -s
```

32 tests: mechanics, conservation invariants, the two customer stories
(drift vs. bid-shock), the structural retailer P&L, and the calibration gate.

## Note on data & framing

Stylized market, illustrative index-unit figures calibrated from public
benchmarks. No client or employer data. Programs modeled on proportionally
equal terms. All companies and figures are fictional.
