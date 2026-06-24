import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Configuration & default case template
# ---------------------------------------------------------------------------
DEFAULT_CASE = {
    "method": "Analytical",
    "well_depth": 5000.0,
    "p_wh": 200.0,
    "p_ko": 900.0,
    "p_so": 850.0,
    "g_s": 0.5,
    "g_u": 0.15,
    "sfl": 0.0,
    "valve_depths": [],
    # Phase 1 — Fluid properties
    "oil_api_gravity": 35.0,
    "gas_gravity": 0.65,
    "water_cut_percent": 50.0,
    "solution_gor": 500.0,
    "separator_pressure_psi": 100.0,
    # Phase 2 — Temperature profile
    "surface_temp_f": 90.0,
    "bht_f": 200.0,
    "thermal_gradient_f_per_1000ft": 12.22,
}

REFERENCE_TEMP_F = 60.0


def ensure_case_defaults(cases: dict) -> None:
    """Merge missing keys from DEFAULT_CASE into every stored case."""
    for case in cases.values():
        for key, value in DEFAULT_CASE.items():
            case.setdefault(key, value)


# ---------------------------------------------------------------------------
# Step 1 — State initialization
# ---------------------------------------------------------------------------
if "gas_lift_cases" not in st.session_state:
    st.session_state.gas_lift_cases = {
        "Base Case (Analytical)": {
            **DEFAULT_CASE,
            "method": "Analytical",
            "well_depth": 5000.0,
            "p_wh": 200.0,
            "p_ko": 900.0,
            "p_so": 850.0,
            "g_s": 0.5,
            "g_u": 0.15,
            "sfl": 0.0,
            "valve_depths": [1800.0, 3111.0, 4013.1],
            "oil_api_gravity": 35.0,
            "gas_gravity": 0.6,
            "water_cut_percent": 50.0,
            "solution_gor": 500.0,
            "separator_pressure_psi": 100.0,
            "surface_temp_f": 90.0,
            "bht_f": 180.0,
            "thermal_gradient_f_per_1000ft": 18.0,
        },
        "Base Case (Graphical)": {
            **DEFAULT_CASE,
            "method": "Graphical",
            "well_depth": 8000.0,
            "p_wh": 100.0,
            "p_ko": 1000.0,
            "p_so": 950.0,
            "g_s": 0.5,
            "g_u": 0.125,
            "sfl": 3407.0,
            "valve_depths": [3407.0, 3900.0, 4400.0, 4700.0],
            "oil_api_gravity": 40.0,
            "gas_gravity": 0.65,
            "water_cut_percent": 90.0,
            "solution_gor": 500.0,
            "separator_pressure_psi": 100.0,
            "surface_temp_f": 90.0,
            "bht_f": 200.0,
            "thermal_gradient_f_per_1000ft": 13.75,
        },
    }

ensure_case_defaults(st.session_state.gas_lift_cases)


# ---------------------------------------------------------------------------
# Phase 3 — Fluid property & temperature utility functions
# ---------------------------------------------------------------------------
def calculate_temperature_at_depth(
    depth_ft: float,
    surface_temp_f: float,
    bht_f: float,
    well_depth_ft: float,
) -> float:
    """Linear interpolation between surface and bottom-hole temperature."""
    if well_depth_ft <= 0:
        return surface_temp_f
    fraction = min(max(depth_ft / well_depth_ft, 0.0), 1.0)
    return surface_temp_f + (bht_f - surface_temp_f) * fraction


def auto_thermal_gradient(surface_temp_f: float, bht_f: float, well_depth_ft: float) -> float:
    """Compute geothermal gradient (°F / 1000 ft) from surface and BHT."""
    if well_depth_ft <= 0:
        return DEFAULT_CASE["thermal_gradient_f_per_1000ft"]
    return (bht_f - surface_temp_f) / (well_depth_ft / 1000.0)


def calculate_z_factor(pressure_psi: float, temperature_f: float, gas_gravity: float) -> float:
    """Papay Z-factor correlation for natural gas."""
    if pressure_psi <= 0:
        return 1.0
    t_pc = 168.0 + 325.0 * gas_gravity - 12.5 * gas_gravity**2
    p_pc = 677.0 + 15.0 * gas_gravity - 37.5 * gas_gravity**2
    t_pr = (temperature_f + 460.0) / t_pc
    p_pr = pressure_psi / p_pc
    exponent = 10.0**t_pr
    z = 1.0 - (3.52 * p_pr / exponent) + (0.274 * p_pr**2 / exponent)
    return float(np.clip(z, 0.2, 1.5))


def calculate_gas_density(
    pressure_psi: float,
    temperature_f: float,
    gas_gravity: float,
) -> float:
    """Real-gas density (lb/ft³) using Z-factor correction."""
    z = calculate_z_factor(pressure_psi, temperature_f, gas_gravity)
    t_rankine = temperature_f + 460.0
    mw = 29.0 * gas_gravity
    # ρ = P·MW / (Z·R·T), R = 10.7316 psia·ft³/(lb-mol·°R)
    return (pressure_psi * mw) / (z * 10.7316 * t_rankine)


def oil_density_from_api(oil_api: float) -> float:
    """Oil density (lb/ft³) at stock-tank conditions from °API."""
    sg_oil = 141.5 / (oil_api + 131.5)
    return sg_oil * 62.4


def calculate_mixture_density(
    oil_api: float,
    water_cut_percent: float,
    gas_gor: float,
    pressure_psi: float,
    temperature_f: float,
    gas_gravity: float,
    separator_pressure_psi: float = 100.0,
) -> float:
    """Mixture density accounting for oil, water, and dissolved gas."""
    rho_oil = oil_density_from_api(oil_api)
    rho_water = 62.4
    wc = water_cut_percent / 100.0
    rho_liquid = rho_oil * (1.0 - wc) + rho_water * wc

    # Standing-style dissolved gas correction (simplified for assignment-level design)
    p_sep = max(separator_pressure_psi, 14.7)
    rs = min(gas_gor, gas_gor * (pressure_psi / p_sep) ** 0.83)
    bg = 0.0283 * gas_gravity * (temperature_f + 460.0) / max(pressure_psi, 14.7)
    vol_gas = rs * bg
    vol_oil = 5.615
    gas_liquid_ratio = vol_gas / (vol_oil + vol_gas)
    rho_g = calculate_gas_density(pressure_psi, temperature_f, gas_gravity)
    rho_mix = rho_liquid * (1.0 - gas_liquid_ratio) + rho_g * gas_liquid_ratio
    return float(max(rho_mix, 40.0))


def calculate_effective_gradient(mixture_density_lb_per_ft3: float) -> float:
    """Convert mixture density to hydrostatic gradient (psi/ft)."""
    return mixture_density_lb_per_ft3 / 144.0


def get_temperature_corrected_gradient(
    base_gradient: float,
    surface_temp: float,
    depth_temp: float,
    reference_temp: float = REFERENCE_TEMP_F,
) -> float:
    """Temperature correction factor per Assignment 02 methodology."""
    t_ref_r = reference_temp + 460.0
    t_avg_r = ((surface_temp + depth_temp) / 2.0) + 460.0
    correction_factor = t_ref_r / t_avg_r
    return base_gradient * correction_factor


def casing_gradient_at_valve_count(g_s: float, valves_installed: int) -> float:
    """Operating casing gas gradient with 0.022 psi/ft shift per valve."""
    return g_s - 0.022 * max(valves_installed - 1, 0)


def recommend_valve_type(depth_ft: float, pressure_margin: float) -> tuple[str, float]:
    """Heuristic valve selection based on depth and available pressure margin."""
    if depth_ft < 2500:
        return "1/4\" IPO", 0.31
    if depth_ft < 4500:
        return "5/16\" IPO", 0.48
    if depth_ft < 6500:
        return "3/8\" IPO", 0.69
    if pressure_margin > 150:
        return "1/2\" Orifice", 1.00
    return "7/16\" IPO", 0.84


# ---------------------------------------------------------------------------
# Core gas lift engines
# ---------------------------------------------------------------------------
def analytical_engine(case: dict) -> list[float]:
    """Calculate valve depths using the analytical spacing formula."""
    p_ko = case.get("p_ko", 900.0)
    p_so = case.get("p_so", 850.0)
    p_wh = case.get("p_wh", 200.0)
    g_s = case.get("g_s", 0.5)
    g_u = case.get("g_u", 0.15)
    well_depth = case.get("well_depth", 5000.0)

    if g_s <= 0:
        return []

    dv1 = p_ko / g_s
    if dv1 > well_depth:
        return [round(dv1, 1)]

    depths = [dv1]
    depth_current = dv1
    p_so_current = p_so

    while True:
        delta_depth = (p_so_current - (g_u * depth_current) - p_wh) / g_s
        if delta_depth <= 0:
            break
        depth_next = depth_current + delta_depth
        if depth_next > well_depth:
            break
        depths.append(depth_next)
        depth_current = depth_next
        p_so_current -= 25.0

    return [round(d, 1) for d in depths]


def _p_casing(depth: float, p_ko: float, g_s: float, valves_installed: int) -> float:
    gradient = casing_gradient_at_valve_count(g_s, valves_installed)
    return p_ko + gradient * depth


def _p_kill(depth: float, p_so: float, g_u: float, p_wh: float) -> float:
    return p_so + g_u * depth


def _find_intersection(
    start_depth: float,
    end_depth: float,
    p_ko: float,
    p_so: float,
    g_s: float,
    g_u: float,
    p_wh: float,
    valves_installed: int,
    step: float = 1.0,
) -> float | None:
    prev_d = start_depth
    prev_diff = _p_kill(prev_d, p_so, g_u, p_wh) - _p_casing(
        prev_d, p_ko, g_s, valves_installed
    )

    d = start_depth + step
    while d <= end_depth:
        curr_diff = _p_kill(d, p_so, g_u, p_wh) - _p_casing(d, p_ko, g_s, valves_installed)
        if prev_diff == 0:
            return round(d, 1)
        if prev_diff * curr_diff <= 0:
            if curr_diff == prev_diff:
                return round(d, 1)
            frac = prev_diff / (prev_diff - curr_diff)
            return round(prev_d + frac * step, 1)
        prev_d = d
        prev_diff = curr_diff
        d += step
    return None


def graphical_engine(case: dict) -> list[float]:
    well_depth = case.get("well_depth", 8000.0)
    p_wh = case.get("p_wh", 100.0)
    p_ko = case.get("p_ko", 1000.0)
    p_so = case.get("p_so", 950.0)
    g_s = case.get("g_s", 0.5)
    g_u = case.get("g_u", 0.125)
    sfl = case.get("sfl", 0.0)

    design_limit = min(5550.0, well_depth)
    if sfl <= 0 or sfl > design_limit:
        return []

    depths = [round(sfl, 1)]
    p_so_current = p_so
    valves_installed = 1

    while True:
        last_depth = depths[-1]
        if last_depth >= design_limit:
            break
        p_so_current -= 25.0
        valves_installed += 1
        intersection = _find_intersection(
            start_depth=last_depth + 1.0,
            end_depth=design_limit,
            p_ko=p_ko,
            p_so=p_so_current,
            g_s=g_s,
            g_u=g_u,
            p_wh=p_wh,
            valves_installed=valves_installed,
        )
        if intersection is None or intersection <= last_depth:
            break
        depths.append(intersection)

    return depths


def run_engine(case: dict) -> list[float]:
    method = case.get("method", "Analytical")
    if method == "Graphical":
        return graphical_engine(case)
    return analytical_engine(case)


# ---------------------------------------------------------------------------
# Phase 4 — Detailed calculation builders
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def build_pressure_detail_rows(case_key: str, case_tuple: tuple) -> pd.DataFrame:
    """Build step-by-step pressure table at key depths (cached by case snapshot)."""
    case = dict(case_tuple)
    well_depth = case.get("well_depth", 5000.0)
    valves = case.get("valve_depths", [])
    key_depths = sorted({0.0, well_depth, *valves})

    rows = []
    for depth in key_depths:
        valves_above = sum(1 for v in valves if v <= depth)
        p_ko = case.get("p_ko", 900.0)
        p_so = case.get("p_so", 850.0)
        g_s = case.get("g_s", 0.5)
        g_u = case.get("g_u", 0.15)
        p_wh = case.get("p_wh", 200.0)

        temp_f = calculate_temperature_at_depth(
            depth,
            case.get("surface_temp_f", 90.0),
            case.get("bht_f", 200.0),
            well_depth,
        )
        est_pressure = case.get("p_wh", 200.0) + g_u * depth
        rho_mix = calculate_mixture_density(
            case.get("oil_api_gravity", 35.0),
            case.get("water_cut_percent", 50.0),
            case.get("solution_gor", 500.0),
            est_pressure,
            temp_f,
            case.get("gas_gravity", 0.65),
            case.get("separator_pressure_psi", 100.0),
        )
        base_grad = calculate_effective_gradient(rho_mix)
        corr_grad = get_temperature_corrected_gradient(
            base_grad,
            case.get("surface_temp_f", 90.0),
            temp_f,
        )
        g_casing = casing_gradient_at_valve_count(g_s, max(valves_above, 1))
        p_so_at_d = p_so - 25.0 * max(valves_above - 1, 0)
        p_c = _p_casing(depth, p_ko, g_s, max(valves_above, 1))
        p_t = _p_kill(depth, p_so_at_d, g_u, p_wh)

        rows.append(
            {
                "Depth (ft)": round(depth, 1),
                "Temp (°F)": round(temp_f, 1),
                "Mixture ρ (lb/ft³)": round(rho_mix, 2),
                "Base Gradient (psi/ft)": round(base_grad, 4),
                "Temp-Corrected Grad (psi/ft)": round(corr_grad, 4),
                "Casing Grad (psi/ft)": round(g_casing, 4),
                "P_casing (psi)": round(p_c, 1),
                "P_tubing (psi)": round(p_t, 1),
                "Valves Above": valves_above,
            }
        )
    return pd.DataFrame(rows)


def build_valve_summary(case: dict) -> pd.DataFrame:
    """Valve-by-valve design summary with pressures and selection rationale."""
    valves = case.get("valve_depths", [])
    if not valves:
        return pd.DataFrame()

    well_depth = case.get("well_depth", 5000.0)
    p_ko = case.get("p_ko", 900.0)
    p_so = case.get("p_so", 850.0)
    g_s = case.get("g_s", 0.5)
    g_u = case.get("g_u", 0.15)
    p_wh = case.get("p_wh", 200.0)

    rows = []
    for i, depth in enumerate(valves, start=1):
        p_so_valve = p_so - 25.0 * (i - 1)
        p_c = _p_casing(depth, p_ko, g_s, i)
        p_t = _p_kill(depth, p_so_valve, g_u, p_wh)
        margin = p_c - p_t
        valve_type, coefficient = recommend_valve_type(depth, margin)
        temp_f = calculate_temperature_at_depth(
            depth,
            case.get("surface_temp_f", 90.0),
            case.get("bht_f", 200.0),
            well_depth,
        )
        rows.append(
            {
                "Valve #": i,
                "Depth (ft)": round(depth, 1),
                "Temp (°F)": round(temp_f, 1),
                "P_casing (psi)": round(p_c, 1),
                "P_tubing (psi)": round(p_t, 1),
                "Pressure Margin (psi)": round(margin, 1),
                "Valve Type": valve_type,
                "Port Coefficient (in²)": coefficient,
                "Selection Rationale": (
                    f"Depth {depth:,.0f} ft; margin {margin:.0f} psi supports {valve_type}"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_fluid_property_summary(case: dict) -> pd.DataFrame:
    """Fluid properties at surface, each valve, and total depth."""
    well_depth = case.get("well_depth", 5000.0)
    valves = case.get("valve_depths", [])
    sample_depths = sorted({0.0, well_depth, *valves})

    rho_oil = oil_density_from_api(case.get("oil_api_gravity", 35.0))
    rho_water = 62.4

    rows = []
    for depth in sample_depths:
        temp_f = calculate_temperature_at_depth(
            depth,
            case.get("surface_temp_f", 90.0),
            case.get("bht_f", 200.0),
            well_depth,
        )
        est_p = case.get("p_wh", 200.0) + case.get("g_u", 0.15) * depth
        rho_g = calculate_gas_density(est_p, temp_f, case.get("gas_gravity", 0.65))
        rho_mix = calculate_mixture_density(
            case.get("oil_api_gravity", 35.0),
            case.get("water_cut_percent", 50.0),
            case.get("solution_gor", 500.0),
            est_p,
            temp_f,
            case.get("gas_gravity", 0.65),
            case.get("separator_pressure_psi", 100.0),
        )
        base_grad = calculate_effective_gradient(rho_mix)
        corr_grad = get_temperature_corrected_gradient(
            base_grad,
            case.get("surface_temp_f", 90.0),
            temp_f,
        )
        rows.append(
            {
                "Depth (ft)": round(depth, 1),
                "Temp (°F)": round(temp_f, 1),
                "Oil ρ (lb/ft³)": round(rho_oil, 2),
                "Water ρ (lb/ft³)": rho_water,
                "Gas ρ (lb/ft³)": round(rho_g, 4),
                "Mixture ρ (lb/ft³)": round(rho_mix, 2),
                "Effective Gradient (psi/ft)": round(base_grad, 4),
                "Temp-Corrected Gradient (psi/ft)": round(corr_grad, 4),
                "Solution GOR (scf/bbl)": case.get("solution_gor", 500.0),
                "Water Cut (%)": case.get("water_cut_percent", 50.0),
            }
        )
    return pd.DataFrame(rows)


def case_to_cache_tuple(case: dict) -> tuple:
    """Hashable snapshot of case dict for cache keys."""
    keys = sorted(case.keys())
    return tuple((k, case[k]) for k in keys if k != "valve_depths") + (
        ("valve_depths", tuple(case.get("valve_depths", []))),
    )


# ---------------------------------------------------------------------------
# Continuous evaluation
# ---------------------------------------------------------------------------
def evaluate_all_cases() -> None:
    for case_name in st.session_state.gas_lift_cases:
        case = st.session_state.gas_lift_cases[case_name]
        case["valve_depths"] = run_engine(case)


evaluate_all_cases()

# ---------------------------------------------------------------------------
# Sidebar & case management
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Continuous Gas Lift Design Dashboard",
    page_icon="🛢️",
    layout="wide",
)

st.title("🛢️ Continuous Gas Lift Design Automation Dashboard")
st.markdown(
    "Interactive continuous gas lift valve spacing design using "
    "**Analytical** and **Graphical** calculation engines with "
    "**fluid property** and **temperature correction** support."
)

st.divider()

case_names = list(st.session_state.gas_lift_cases.keys())

with st.sidebar:
    st.header("Case Management")
    active_case = st.selectbox("Active Case", case_names, key="active_case_select")

    st.divider()
    st.subheader("Create New Case")
    new_case_name = st.text_input("New case name", placeholder="e.g. Scenario A")

    if st.button("➕ Create & Save New Case", use_container_width=True):
        name = new_case_name.strip()
        if not name:
            st.warning("Enter a case name before creating.")
        elif name in st.session_state.gas_lift_cases:
            st.warning(f"Case **{name}** already exists.")
        else:
            st.session_state.gas_lift_cases[name] = dict(DEFAULT_CASE)
            st.session_state.active_case_select = name
            st.rerun()

    st.divider()
    st.subheader("Active Case Configuration")

    if active_case and active_case in st.session_state.gas_lift_cases:
        active = st.session_state.gas_lift_cases[active_case]

        active["method"] = st.radio(
            "Design Method",
            ["Analytical", "Graphical"],
            index=0 if active.get("method", "Analytical") == "Analytical" else 1,
            key=f"method_{active_case}",
        )

        st.markdown("**Well & Pressure Parameters**")
        active["well_depth"] = st.number_input(
            "Well Depth (ft)",
            min_value=100.0,
            max_value=20000.0,
            value=float(active.get("well_depth", 5000.0)),
            step=50.0,
            key=f"well_depth_{active_case}",
        )
        active["p_wh"] = st.number_input(
            "Wellhead Pressure P_wh (psi)",
            min_value=0.0,
            max_value=5000.0,
            value=float(active.get("p_wh", 200.0)),
            step=10.0,
            key=f"p_wh_{active_case}",
        )
        active["p_ko"] = st.number_input(
            "Kickoff Pressure P_ko (psi)",
            min_value=0.0,
            max_value=5000.0,
            value=float(active.get("p_ko", 900.0)),
            step=10.0,
            key=f"p_ko_{active_case}",
        )
        active["p_so"] = st.number_input(
            "Surface Operating P_so (psi)",
            min_value=0.0,
            max_value=5000.0,
            value=float(active.get("p_so", 850.0)),
            step=10.0,
            key=f"p_so_{active_case}",
        )
        active["g_s"] = st.number_input(
            "Gas Gradient g_s (psi/ft)",
            min_value=0.01,
            max_value=2.0,
            value=float(active.get("g_s", 0.5)),
            step=0.01,
            format="%.3f",
            key=f"g_s_{active_case}",
        )
        active["g_u"] = st.number_input(
            "Tubing Gradient g_u (psi/ft)",
            min_value=0.01,
            max_value=2.0,
            value=float(active.get("g_u", 0.15)),
            step=0.01,
            format="%.3f",
            key=f"g_u_{active_case}",
        )
        active["sfl"] = st.number_input(
            "Static Fluid Level SFL (ft)",
            min_value=0.0,
            max_value=20000.0,
            value=float(active.get("sfl", 0.0)),
            step=50.0,
            key=f"sfl_{active_case}",
            help="Used by the Graphical method for Valve 1 depth.",
        )

        st.divider()
        st.markdown("**Fluid Properties**")
        active["oil_api_gravity"] = st.number_input(
            "Oil API Gravity (°API)",
            min_value=5.0,
            max_value=70.0,
            value=float(active.get("oil_api_gravity", 35.0)),
            step=0.5,
            key=f"oil_api_{active_case}",
            help="API gravity of produced crude oil",
        )
        active["gas_gravity"] = st.number_input(
            "Gas Gravity (relative to air)",
            min_value=0.5,
            max_value=2.0,
            value=float(active.get("gas_gravity", 0.65)),
            step=0.05,
            format="%.2f",
            key=f"gas_grav_{active_case}",
            help="Specific gravity of lift gas",
        )
        active["water_cut_percent"] = st.number_input(
            "Water Cut (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(active.get("water_cut_percent", 50.0)),
            step=5.0,
            key=f"water_cut_{active_case}",
            help="Percentage water in produced fluids",
        )
        active["solution_gor"] = st.number_input(
            "Solution GOR (scf/bbl)",
            min_value=0.0,
            max_value=3000.0,
            value=float(active.get("solution_gor", 500.0)),
            step=50.0,
            key=f"solution_gor_{active_case}",
            help="Solution gas-oil ratio at bubble point",
        )
        active["separator_pressure_psi"] = st.number_input(
            "Separator Pressure (psi)",
            min_value=0.0,
            max_value=2000.0,
            value=float(active.get("separator_pressure_psi", 100.0)),
            step=10.0,
            key=f"sep_p_{active_case}",
            help="Surface separator operating pressure",
        )

        st.divider()
        st.markdown("**Temperature Profile**")
        active["surface_temp_f"] = st.number_input(
            "Surface Temperature (°F)",
            min_value=40.0,
            max_value=120.0,
            value=float(active.get("surface_temp_f", 90.0)),
            step=5.0,
            key=f"surf_temp_{active_case}",
        )
        active["bht_f"] = st.number_input(
            "Bottom Hole Temperature (°F)",
            min_value=100.0,
            max_value=400.0,
            value=float(active.get("bht_f", 200.0)),
            step=5.0,
            key=f"bht_{active_case}",
            help="Estimated temperature at well total depth",
        )

        computed_gradient = auto_thermal_gradient(
            active.get("surface_temp_f", 90.0),
            active.get("bht_f", 200.0),
            active.get("well_depth", 5000.0),
        )
        st.caption(f"Auto-calculated gradient: **{computed_gradient:.2f} °F / 1000 ft**")

        active["thermal_gradient_f_per_1000ft"] = st.number_input(
            "Thermal Gradient (°F / 1000 ft)",
            min_value=1.0,
            max_value=50.0,
            value=float(active.get("thermal_gradient_f_per_1000ft", computed_gradient)),
            step=0.5,
            key=f"thermal_grad_{active_case}",
            help="Temperature increase per 1000 ft depth (auto-calculated from BHT if unchanged)",
        )

evaluate_all_cases()

active = st.session_state.gas_lift_cases.get(active_case, {})
active_valves = active.get("valve_depths", [])
deepest_valve = max(active_valves) if active_valves else 0.0

# ---------------------------------------------------------------------------
# Main area — Design summary
# ---------------------------------------------------------------------------
st.header("Design Summary")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Case", active_case)
col2.metric("Design Method", active.get("method", "—"))
col3.metric("Total Valves", len(active_valves))
col4.metric("Deepest Valve (ft)", f"{deepest_valve:,.1f}")

st.divider()

st.header("All Cases — Valve Depth Results")

summary_rows = []
for name, case in st.session_state.gas_lift_cases.items():
    valves = case.get("valve_depths", [])
    summary_rows.append(
        {
            "Case": name,
            "Method": case.get("method", "—"),
            "Well Depth (ft)": case.get("well_depth", 0.0),
            "API Gravity": case.get("oil_api_gravity", 35.0),
            "Water Cut (%)": case.get("water_cut_percent", 50.0),
            "Valve Count": len(valves),
            "Deepest Valve (ft)": max(valves) if valves else None,
            "Valve Depths (ft)": ", ".join(f"{v:,.1f}" for v in valves) if valves else "—",
        }
    )

st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

st.divider()

st.header("Active Case — Valve Detail")

if active_valves:
    valve_df = pd.DataFrame(
        {
            "Valve #": range(1, len(active_valves) + 1),
            "Depth (ft)": active_valves,
            "Spacing from Previous (ft)": [
                active_valves[0],
                *[active_valves[i] - active_valves[i - 1] for i in range(1, len(active_valves))],
            ],
        }
    )
    st.dataframe(valve_df, use_container_width=True, hide_index=True)
else:
    st.info("No valves calculated for the active case with current inputs.")

# ---------------------------------------------------------------------------
# Phase 4 — Calculation Details & Validation
# ---------------------------------------------------------------------------
st.divider()
st.header("Calculation Details & Validation")

with st.expander("Pressure Profile Calculations", expanded=True):
    st.markdown(
        "**Formulas applied:**  \n"
        "- Temperature: `T(D) = T_surface + (T_BHT − T_surface) × (D / TD)`  \n"
        "- Mixture gradient: `grad = ρ_mix / 144` (psi/ft)  \n"
        "- Temperature correction: `grad_corr = grad × (T_ref / T_avg)`  \n"
        "- Casing gradient: `g_casing = g_s − 0.022 × (N_valves − 1)`  \n"
        "- Analytical spacing: `ΔD = (P_so − g_u·D − P_wh) / g_s`"
    )
    if active:
        detail_df = build_pressure_detail_rows(active_case, case_to_cache_tuple(active))
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
    else:
        st.info("Select an active case to view pressure calculations.")

with st.expander("Valve Design Summary"):
    st.markdown(
        "Per-valve casing/tubing pressures, operating margin, and recommended "
        "IPO port size based on depth and available differential pressure."
    )
    valve_summary = build_valve_summary(active)
    if not valve_summary.empty:
        st.dataframe(valve_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No valves to summarize for the active case.")

with st.expander("Fluid Property Summary"):
    st.markdown(
        "**Property models:**  \n"
        "- Oil density: `ρ_oil = (141.5 / (API + 131.5)) × 62.4` lb/ft³  \n"
        "- Gas density: real-gas law with Papay Z-factor  \n"
        "- Mixture: oil/water blend with dissolved-gas volume correction"
    )
    fluid_df = build_fluid_property_summary(active)
    if not fluid_df.empty:
        st.dataframe(fluid_df, use_container_width=True, hide_index=True)

        col_a, col_b, col_c = st.columns(3)
        surface_row = fluid_df.iloc[0]
        col_a.metric("Surface Mixture ρ", f"{surface_row['Mixture ρ (lb/ft³)']:.2f} lb/ft³")
        col_b.metric("Surface Gas ρ", f"{surface_row['Gas ρ (lb/ft³)']:.4f} lb/ft³")
        col_c.metric(
            "Thermal Gradient",
            f"{active.get('thermal_gradient_f_per_1000ft', 12.22):.2f} °F/1000ft",
        )
    else:
        st.info("No fluid property data available.")

# ---------------------------------------------------------------------------
# Pressure profile visualization
# ---------------------------------------------------------------------------
st.divider()
st.header("Pressure Profile Matrix")


def build_pressure_profiles(case: dict) -> tuple[list[float], list[float], list[float]]:
    well_depth = case.get("well_depth", 5000.0)
    depths = list(range(0, int(well_depth) + 1, 25))
    if depths[-1] != int(well_depth):
        depths.append(int(well_depth))

    p_ko = case.get("p_ko", 900.0)
    p_so = case.get("p_so", 850.0)
    g_s = case.get("g_s", 0.5)
    g_u = case.get("g_u", 0.15)
    p_wh = case.get("p_wh", 200.0)
    valves = case.get("valve_depths", [])

    p_casing = []
    p_kill = []

    for d in depths:
        valves_above = sum(1 for v in valves if v <= d)
        p_casing.append(_p_casing(d, p_ko, g_s, max(valves_above, 1)))
        p_so_at_d = p_so - 25.0 * max(valves_above - 1, 0)
        p_kill.append(_p_kill(d, p_so_at_d, g_u, p_wh))

    return depths, p_casing, p_kill


fig = go.Figure()

case_colors = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]

for idx, (name, case) in enumerate(st.session_state.gas_lift_cases.items()):
    color = case_colors[idx % len(case_colors)]
    depths, p_casing, p_kill = build_pressure_profiles(case)

    fig.add_trace(
        go.Scatter(
            x=p_casing,
            y=depths,
            mode="lines",
            name=f"{name} — Casing",
            line=dict(color=color, width=2),
            legendgroup=name,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=p_kill,
            y=depths,
            mode="lines",
            name=f"{name} — Kill/Tubing",
            line=dict(color=color, width=2, dash="dot"),
            legendgroup=name,
        )
    )

all_valve_depths: set[float] = set()
for case in st.session_state.gas_lift_cases.values():
    for vd in case.get("valve_depths", []):
        all_valve_depths.add(vd)

x_max = max(
    [
        max(p_casing)
        for _, case in st.session_state.gas_lift_cases.items()
        for _, p_casing, _ in [build_pressure_profiles(case)]
    ]
    + [1000.0]
)

for vd in sorted(all_valve_depths):
    fig.add_shape(
        type="line",
        x0=0,
        x1=x_max * 1.05,
        y0=vd,
        y1=vd,
        line=dict(color="rgba(120, 120, 120, 0.55)", width=1, dash="dash"),
        layer="below",
    )

fig.update_layout(
    title="Continuous Gas Lift — Pressure vs. True Vertical Depth",
    height=650,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=60, r=40, t=80, b=60),
    hovermode="closest",
)

fig.update_yaxes(autorange="reversed", title_text="True Vertical Depth (ft)")
fig.update_xaxes(title_text="Pressure Profile Matrix (psi / psig)")

st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(
    "Valve depths are recalculated continuously for every case whenever inputs change. "
    "Fluid properties and temperature corrections are applied in the Calculation Details section."
)
