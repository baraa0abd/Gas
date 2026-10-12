# SeparatorSizer Pro

A petroleum separator sizing tool for 2-phase and 3-phase, vertical or horizontal separators, using the Chapter 4 Separator correlations (Dr. Abdul Rahim Risal, UTM).

## Quick start

```bash
git clone https://github.com/baraa0abd/Gas.git
cd Gas
pip install -r requirements.txt
streamlit run app.py
```

## What it does

Given fluid properties and flow rates, it sizes separator vessels using standard petroleum engineering correlations:

- **Inputs:** API gravity, gas/water specific gravity, pressure, temperature, Z-factor, and flow rates (gas in MMscfd, oil in BOPD, water in BPD).
- **Computes:** fluid densities (oil, water, gas) from the input properties, then sizes the separator using the UTM Ch.4 correlations for both 2-phase (gas/liquid) and 3-phase (gas/oil/water) separation, in vertical or horizontal configuration.
- The same sizing engine (`backend/separator_engine.py`) backs both the Streamlit UI and an optional Flask/React stack in `frontend/`, so the calculation logic isn't duplicated between interfaces.

## Tech stack

Python (sizing engine + Streamlit UI), with an optional Flask + React frontend as an alternate interface to the same engine.

## Deploy

Live on Streamlit Community Cloud:

1. Push to GitHub: [baraa0abd/Gas](https://github.com/baraa0abd/Gas)
2. Sign in at [share.streamlit.io](https://share.streamlit.io)
3. **Create app** → select `baraa0abd/Gas`, branch `main`, main file `app.py`
4. Deploy — live at a `*.streamlit.app` URL

See the [Streamlit deployment docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started) for details.

## Project structure

```
Gas/
├── app.py                        # Streamlit UI
├── backend/
│   ├── separator_engine.py       # Sizing correlations (shared by both UIs)
│   └── app.py                    # Flask API, for the frontend/ React alternative
└── frontend/                     # Optional React UI consuming the Flask API
```

## License

No license file is currently included.
