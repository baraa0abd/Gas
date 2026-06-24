import streamlit as st
import plotly.graph_objects as go
import pandas as pd

# ---------------------------------------------------------------------------
# Step 1 — State initialization
# ---------------------------------------------------------------------------
if "gas_lift_cases" not in st.session_state:
    st.session_state.gas_lift_cases = {
        "Base Case (Analytical)": {
            "method": "Analytical",
            "well_depth": 5000.0,
            "p_wh": 200.0,
            "p_ko": 900.0,
            "p_so": 850.0,
            "g_s": 0.5,
            "g_u": 0.15,
            "sfl": 0.0,
            "valve_depths": [1800.0, 3111.0, 4013.1],
        },
        "Base Case (Graphical)": {
            "method": "Graphical",
            "well_depth": 8000.0,
            "p_wh": 100.0,
            "p_ko": 1000.0,
            "p_so": 950.0,
            "g_s": 0.5,
            "g_u": 0.125,
            "sfl": 3407.0,
            "valve_depths": [3407.0, 3900.0, 4400.0, 4700.0],
        },
    }

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
}


# ---------------------------------------------------------------------------
# Step 3 — Mathematical engines
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
    """Casing pressure at depth with per-valve gradient shift."""
    gradient = g_s - 0.022 * max(valves_installed - 1, 0)
    return p_ko + gradient * depth


def _p_kill(depth: float, p_so: float, g_u: float, p_wh: float) -> float:
    """Tubing / kill-oil pressure at depth (surface operating + liquid gradient)."""
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
    """Scan depth range and return first intersection of P_kill and P_casing."""
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
            # Linear interpolation for finer intersection
            if curr_diff == prev_diff:
                return round(d, 1)
            frac = prev_diff / (prev_diff - curr_diff)
            return round(prev_d + frac * step, 1)
        prev_d = d
        prev_diff = curr_diff
        d += step

    return None


def graphical_engine(case: dict) -> list[float]:
    """Calculate valve depths via P_kill / P_casing intersection method."""
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
    """Route a case to its assigned calculation engine."""
    method = case.get("method", "Analytical")
    if method == "Graphical":
        return graphical_engine(case)
    return analytical_engine(case)


# ---------------------------------------------------------------------------
# Step 4 — Continuous evaluation over all cases
# ---------------------------------------------------------------------------
def evaluate_all_cases() -> None:
    for case_name in st.session_state.gas_lift_cases:
        case = st.session_state.gas_lift_cases[case_name]
        case["valve_depths"] = run_engine(case)


evaluate_all_cases()

# ---------------------------------------------------------------------------
# Step 2 — Sidebar & case management
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Continuous Gas Lift Design Dashboard",
    page_icon="🛢️",
    layout="wide",
)

st.title("🛢️ Continuous Gas Lift Design Automation Dashboard")
st.markdown(
    "Interactive continuous gas lift valve spacing design using "
    "**Analytical** and **Graphical** calculation engines."
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

# Re-evaluate after sidebar mutations
evaluate_all_cases()

active = st.session_state.gas_lift_cases.get(active_case, {})
active_valves = active.get("valve_depths", [])
deepest_valve = max(active_valves) if active_valves else 0.0

# ---------------------------------------------------------------------------
# Step 5 — UI rendering & visualization
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

st.divider()

st.header("Pressure Profile Matrix")


def build_pressure_profiles(case: dict) -> tuple[list[float], list[float], list[float]]:
    """Return depth grid, casing pressures, and kill-oil pressures for plotting."""
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
        # Tubing line uses current operating P_so reduced by 25 psi per installed valve
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

# Horizontal dashed reference lines for every valve depth across all scenarios
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
    "Dashed horizontal lines mark valve depths across all scenarios for side-by-side comparison."
)
