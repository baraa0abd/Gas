import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

_APP_DIR = Path(__file__).resolve().parent
_BACKEND = _APP_DIR / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from separator_engine import recommend_retention_minutes, run_sizing  # noqa: E402

st.set_page_config(
    page_title="SeparatorSizer Pro",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("SeparatorSizer Pro")
st.caption("2/3-phase separator design · UTM Ch.4 correlations (Dr. Abdul Rahim Risal)")

with st.sidebar:
    st.header("Configuration")
    separator_type = st.radio("Separator type", ["vertical", "horizontal"], horizontal=True)
    phase_mode = st.radio("Phase mode", ["2-phase", "3-phase"], horizontal=True)

    st.subheader("Flow rates")
    gas_mmscfd = st.number_input("Gas rate (MMscfd)", min_value=0.0, value=5.0, step=0.5)
    oil_bopd = st.number_input("Oil rate (BOPD)", min_value=0.0, value=1000.0, step=50.0)
    water_bpd = 0.0
    if phase_mode == "3-phase":
        water_bpd = st.number_input("Water rate (BPD)", min_value=0.0, value=200.0, step=25.0)

    st.subheader("Fluid properties")
    api_gravity = st.number_input("Oil API gravity (°API)", value=35.0, step=1.0)
    sg_gas = st.number_input("Gas specific gravity (air=1)", value=0.65, step=0.01, format="%.3f")
    sg_water = 1.0
    if phase_mode == "3-phase":
        sg_water = st.number_input("Water specific gravity", value=1.0, step=0.01, format="%.3f")
    pressure_psia = st.number_input("Operating pressure (psia)", min_value=0.0, value=800.0, step=10.0)
    temperature_f = st.number_input("Operating temperature (°F)", value=60.0, step=5.0)
    z_factor = st.number_input("Z-factor", min_value=0.1, value=0.83, step=0.01, format="%.3f")

    st.subheader("Design parameters")
    default_k = 0.167 if separator_type == "vertical" else 0.45
    k_factor = st.number_input("K constant", value=default_k, step=0.001, format="%.3f")
    shell_height_ft = 10.0
    liquid_fraction = 0.5
    if separator_type == "vertical":
        shell_height_ft = st.number_input("Shell height (ft)", min_value=5.0, value=10.0, step=1.0)
    else:
        liquid_fraction = st.slider("Liquid fill fraction (f_liq)", 0.25, 0.75, 0.5, 0.05)

    st.subheader("Retention time")
    custom_retention = st.checkbox("Custom retention time")
    oil_rec, water_rec, ret_note = recommend_retention_minutes(phase_mode, pressure_psia, temperature_f)
    if not custom_retention:
        st.info(ret_note)
    retention_oil_min = st.number_input(
        "Oil retention (min)",
        min_value=0.1,
        value=float(oil_rec),
        step=0.5,
        disabled=not custom_retention,
    )
    retention_water_min = retention_oil_min
    if phase_mode == "3-phase":
        retention_water_min = st.number_input(
            "Water retention (min)",
            min_value=0.1,
            value=float(water_rec or oil_rec),
            step=0.5,
            disabled=not custom_retention,
        )

    run = st.button("Run sizing", type="primary", use_container_width=True)

if run:
    payload = {
        "separator_type": separator_type,
        "phase_mode": phase_mode,
        "gas_mmscfd": gas_mmscfd,
        "oil_bopd": oil_bopd,
        "water_bpd": water_bpd,
        "api_gravity": api_gravity,
        "sg_gas": sg_gas,
        "sg_water": sg_water,
        "pressure_psia": pressure_psia,
        "temperature_f": temperature_f,
        "z_factor": z_factor,
        "k_factor": k_factor,
        "shell_height_ft": shell_height_ft,
        "liquid_fraction": liquid_fraction,
        "custom_retention": custom_retention,
        "retention_oil_min": retention_oil_min,
        "retention_water_min": retention_water_min,
    }
    try:
        st.session_state.last_result = run_sizing(payload)["result"]
        st.session_state.last_payload = payload
    except Exception as exc:
        st.error(f"Calculation failed: {exc}")

if "last_result" not in st.session_state:
    st.info("Configure inputs in the sidebar and click **Run sizing**.")
    st.stop()

result = st.session_state.last_result
is_vertical = result["separator_type"] == "vertical"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Diameter", f"{result['diameter_in']:.0f} in")
col2.metric("Length / height", f"{result['length_ft']:.1f} ft")
col3.metric("Liquid height", f"{result['liquid_height_ft']:.2f} ft")
col4.metric("L/D ratio", f"{result['ld_ratio']:.2f}")

st.success(
    f"Recommended: **{result['diameter_in']:.0f}\" × {result['length_ft']:.1f}'** "
    f"{result['separator_type']} separator · Governing: **{result['governing_constraint']}**"
)

left, right = st.columns(2)

with left:
    st.subheader("Design constraints")
    for c in result["constraints"]:
        badge = " (governing)" if c["governing"] else ""
        with st.expander(f"{c['name']}{badge}", expanded=c["governing"]):
            st.code(c["formula"], language=None)
            st.write(
                f"Capacity: **{c['capacity_value']:,.1f}** {c['capacity_unit']} · "
                f"Required dimension: **{c['length_or_height_ft']:.2f}** ft"
            )

with right:
    st.subheader("Fluid properties @ operating conditions")
    st.dataframe(
        pd.DataFrame([{"Property": k.replace("_", " "), "Value": v} for k, v in result["fluid_summary"].items()]),
        hide_index=True,
        use_container_width=True,
    )
    st.subheader("Retention")
    ret = result["retention_summary"]
    st.write(f"Oil: **{ret['oil_minutes']}** min")
    if ret.get("water_minutes") is not None:
        st.write(f"Water: **{ret['water_minutes']}** min")
    if ret.get("note"):
        st.caption(ret["note"])

curve = result.get("curve_data") or []
if curve:
    st.subheader("Capacity curves")
    df = pd.DataFrame(curve)
    x_col = "diameter_in" if is_vertical else "length_ft"
    x_label = "Diameter (in)" if is_vertical else "Length (ft)"

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=df[x_col], y=df["gas_capacity_mmscfd"], name="Gas capacity (MMscfd)", line=dict(color="#38bdf8")),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df[x_col], y=df["oil_capacity_bopd"], name="Oil capacity (BOPD)", line=dict(color="#fbbf24")),
        secondary_y=True,
    )
    if len(df):
        fig.add_hline(y=df["required_gas_mmscfd"].iloc[0], line_dash="dash", line_color="#0ea5e9", secondary_y=False)
        fig.add_hline(y=df["required_oil_bopd"].iloc[0], line_dash="dash", line_color="#f59e0b", secondary_y=True)
    fig.update_xaxes(title_text=x_label)
    fig.update_yaxes(title_text="Gas (MMscfd)", secondary_y=False)
    fig.update_yaxes(title_text="Oil (BOPD)", secondary_y=True)
    fig.update_layout(height=420, margin=dict(l=40, r=40, t=30, b=40), legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)
