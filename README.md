# SeparatorSizer Pro

Web-based petroleum engineering tool for **2-phase and 3-phase separator design**. Calculates vessel dimensions (diameter and length/height), gas/oil/water capacities, and retention time based on feed flow rates and fluid properties.

Engineering correlations follow **Chapter 4 — Separator Part 3** (Dr. Abdul Rahim Risal, UTM).

## Stack

- **Frontend:** React + Tailwind CSS + Recharts
- **Backend:** Python Flask
- **Deployment:** Flask serves the built React SPA, or run Vite dev server with API proxy

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

API runs at `http://localhost:5000`.

### Frontend (development)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — Vite proxies `/api` to Flask.

### Production build

```bash
cd frontend
npm install
npm run build
cd ../backend
python app.py
```

Flask serves the SPA from `frontend/dist`.

## Engineering Formulas

### Fluid properties

| Property | Formula |
|----------|---------|
| Oil SG | `SG_oil = 141.5 / (API + 131.5)` |
| Oil density | `ρ_oil = SG_oil × 62.4 lb/ft³` |
| Gas density | `ρ_gas = (P × M_air × SG_gas) / (Z × R × T)` with R = 10.73, T in °R |

### Retention time (rule of thumb, slide 8)

- Oil/gas only: **1 min**
- Oil/gas/water high pressure (≥500 psia): **2–5 min**
- Oil/gas/water low pressure: temperature-dependent (25–30 min @ 60°F down to 5–10 min @ ≥100°F)

### Vertical separator

- **Oil capacity:** `q_oil = (h × D² × SG_oil) / (0.12 × t_r)` BOPD
- **Gas capacity:** `Q_gas = 0.0119 × K × D² × √((ρ_liq − ρ_g)/ρ_g) × (P×Z)/(T×SG_gas)` MMscfd
- **Liquid height h** from shell-height lookup (slide 10): 5 ft → 2.5 ft, 10 ft → 3.25 ft, 15 ft → 4.25 ft

### Horizontal separator (single barrel)

- **Oil capacity:** `q_oil = (D² × L × SG_oil × f_liq) / (0.1 × t_r)` BOPD
- **Gas capacity:** `Q_gas = 0.0119 × K × D × L × √((ρ_liq − ρ_g)/ρ_g) × (P×Z)/(T×SG_gas) × f_vapor`

## Deployment (Render — same GitHub repo)

This app is a **Flask + React** stack. It replaces the previous Streamlit gas-lift app in this repo.

1. Push to `https://github.com/baraa0abd/Gas`
2. Go to [render.com](https://render.com) → **New +** → **Blueprint** (or Web Service)
3. Connect **baraa0abd/Gas** and deploy using `render.yaml`
4. Render builds the React frontend and runs Flask with Gunicorn
5. Optional: add your custom domain under **Settings → Custom Domains**

If you previously used **Streamlit Cloud** on this repo, disconnect or delete that app — Streamlit cannot run this Flask/React stack.

## API

`POST /api/calculate` — run sizing with JSON body (separator type, flows, fluid properties, retention settings).

`GET /api/retention-recommendation` — recommended retention times for phase mode, pressure, and temperature.
