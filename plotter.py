"""Plotly pressure-depth diagram for gas lift design."""

from __future__ import annotations

import plotly.graph_objects as go

from pressure_engines import (
    calculate_casing_pressure_line,
    calculate_kill_fluid_line,
    calculate_sfl,
    calculate_tubing_pressure_line,
    casing_pressure_at_depth,
    casing_gradient_for_valve_number,
    tubing_pressure_at_depth,
    operating_surface_pressure,
    pressures_at_valve,
    design_limit_from_case,
)
from valve_engine import resolve_sfl


def build_valve_zigzag(case: dict, step: float = 10.0) -> tuple[list[float], list[float]]:
    """Valve unloading zigzag: tubing → horizontal bridge → casing gas diagonal."""
    well_depth = case.get("well_depth", 8000.0)
    plot_depth = design_limit_from_case(case)
    p_wh = case.get("p_wh", 100.0)
    p_ko = case.get("p_ko", 950.0)
    g_s = case.get("g_s", 0.5)
    g_u = case.get("g_u", 0.125)
    valves = case.get("valve_depths", [])

    if not valves:
        return [], []

    import numpy as np

    xs: list[float] = []
    ys: list[float] = []

    def add_line(d_start: float, d_end: float, pressure_fn) -> None:
        if d_end < d_start:
            return
        depths = np.arange(d_start, d_end + step * 0.01, step)
        if depths.size == 0 or depths[-1] < d_end:
            depths = np.append(depths, d_end)
        for d in depths:
            xs.append(float(pressure_fn(d)))
            ys.append(float(d))

    add_line(0.0, valves[0], lambda d: p_wh + g_u * d)

    for i, d_v in enumerate(valves):
        g_si = casing_gradient_for_valve_number(g_s, i + 1)
        p_t = p_wh + g_u * d_v
        p_c = p_ko + g_si * d_v
        xs.extend([p_t, p_c])
        ys.extend([d_v, d_v])
        if i < len(valves) - 1:
            add_line(d_v, valves[i + 1], lambda d, gs=g_si: p_ko + gs * d)
        else:
            end_depth = plot_depth
            if end_depth > d_v:
                add_line(d_v, end_depth, lambda d: p_wh + g_u * d)

    return xs, ys


def plot_pressure_depth_diagram(
    case: dict,
    case_label: str = "",
) -> go.Figure:
    """Build the full gas lift pressure vs depth diagram per UTM methodology."""
    well_depth = float(case.get("well_depth", 8000.0))
    plot_depth = design_limit_from_case(case)
    p_ko = float(case.get("p_ko", 950.0))
    p_so = float(case.get("p_so", 900.0))
    p_wh = float(case.get("p_wh", 100.0))
    g_s = float(case.get("g_s", 0.5))
    g_u = float(case.get("g_u", 0.125))
    valves = case.get("valve_depths", [])
    sfl = resolve_sfl(case)
    wfl = sfl

    prefix = f"{case_label} — " if case_label else ""
    fig = go.Figure()

    # PKO / Casing line (initial, valve 1 condition)
    d_c, p_c = calculate_casing_pressure_line(p_ko, g_s, plot_depth, valve_number=1)
    fig.add_trace(
        go.Scatter(
            x=p_c,
            y=d_c,
            mode="lines",
            name=f"{prefix}PKO (Casing)",
            line=dict(color="#c0392b", width=2.5),
            hovertemplate="PKO<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # PSO line — operating casing reference from P_so
    d_pso, p_pso = calculate_casing_pressure_line(p_so, g_s, plot_depth, valve_number=1)
    fig.add_trace(
        go.Scatter(
            x=p_pso,
            y=d_pso,
            mode="lines",
            name=f"{prefix}PSO",
            line=dict(color="#e74c3c", width=2.0, dash="dot"),
            hovertemplate="PSO<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # Initial tubing / WFL line: Pt(D) = P_so + G_u × D
    d_t, p_t = calculate_tubing_pressure_line(p_so, g_u, plot_depth, valve_number=1)
    fig.add_trace(
        go.Scatter(
            x=p_t,
            y=d_t,
            mode="lines",
            name=f"{prefix}Tubing (Initial / WFL)",
            line=dict(color="#2980b9", width=2.5),
            hovertemplate="Tubing<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # Kill fluid line from surface
    first_valve = valves[0] if valves else max(sfl, 1.0)
    p_ko_at_first = casing_pressure_at_depth(first_valve, p_ko, g_s, 1)
    g_kill = p_ko_at_first / first_valve if first_valve > 0 else g_u
    d_k, p_k = calculate_kill_fluid_line(g_kill, plot_depth, p_surface=0.0)
    fig.add_trace(
        go.Scatter(
            x=p_k,
            y=d_k,
            mode="lines",
            name=f"{prefix}Kill Fluid",
            line=dict(color="#e67e22", width=2.0, dash="dash"),
            hovertemplate="Kill Fluid<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # SFL static gradient reference: P_wh + g_static × D (use g_u as working gradient proxy)
    import numpy as np

    d_sfl = np.arange(0, plot_depth + 1, 25)
    p_sfl_ref = p_wh + (g_u * 1.15) * d_sfl
    fig.add_trace(
        go.Scatter(
            x=p_sfl_ref,
            y=d_sfl,
            mode="lines",
            name=f"{prefix}SFL (Static gradient)",
            line=dict(color="#3498db", width=1.5, dash="dot"),
            hovertemplate="SFL ref<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # Operating tubing lines per valve (dashed blue)
    for n in range(2, len(valves) + 1):
        d_op, p_op = calculate_tubing_pressure_line(p_so, g_u, plot_depth, valve_number=n)
        fig.add_trace(
            go.Scatter(
                x=p_op,
                y=d_op,
                mode="lines",
                name=f"{prefix}Tubing Valve {n}",
                line=dict(color="#5dade2", width=1.2, dash="dot"),
                showlegend=(n <= 4),
                hovertemplate=f"Valve {n} tubing<br>P: %{{x:.1f}} psi<br>D: %{{y:.1f}} ft<extra></extra>",
            )
        )

    # Valve unloading zigzag
    zig_x, zig_y = build_valve_zigzag(case)
    if zig_x and zig_y:
        fig.add_trace(
            go.Scatter(
                x=zig_x,
                y=zig_y,
                mode="lines",
                name=f"{prefix}Valve Unloading Zigzag",
                line=dict(color="#27ae60", width=3.0),
                hovertemplate="Unloading path<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
            )
        )

    # Valve markers at intersection points
    if valves:
        vx, vy, vlabels = [], [], []
        for i, d_v in enumerate(valves, start=1):
            p_c_v, p_t_v = pressures_at_valve(d_v, p_ko, p_so, p_wh, g_s, g_u, i)
            vx.append(p_c_v)
            vy.append(d_v)
            vlabels.append(f"Valve {i}")
        fig.add_trace(
            go.Scatter(
                x=vx,
                y=vy,
                mode="markers+text",
                name=f"{prefix}Valves",
                marker=dict(size=11, color="#1e8449", symbol="circle", line=dict(width=1.5, color="#fff")),
                text=vlabels,
                textposition="middle right",
                textfont=dict(size=10, color="#1e8449"),
                hovertemplate="Valve<br>P_casing: %{x:.1f} psi<br>Depth: %{y:.1f} ft<extra></extra>",
            )
        )

    x_max = max(float(max(p_c)), float(max(p_t)), 500.0)

    # Design limit marker (pressure lines stop here)
    fig.add_shape(
        type="line",
        x0=0,
        x1=x_max * 1.05,
        y0=plot_depth,
        y1=plot_depth,
        line=dict(color="rgba(230, 126, 34, 0.85)", width=2, dash="dash"),
        layer="below",
    )
    fig.add_annotation(
        x=x_max * 0.02,
        y=plot_depth,
        text=f"Design Limit ({plot_depth:,.0f} ft)",
        showarrow=False,
        font=dict(color="#e67e22", size=11),
    )

    # Valve depth reference lines (may extend through full well TD)
    for d_v in valves:
        fig.add_shape(
            type="line",
            x0=0,
            x1=x_max * 1.05,
            y0=d_v,
            y1=d_v,
            line=dict(color="rgba(120, 120, 120, 0.45)", width=1, dash="dash"),
            layer="below",
        )

    if sfl > 0:
        fig.add_shape(
            type="line",
            x0=0,
            x1=x_max * 1.05,
            y0=sfl,
            y1=sfl,
            line=dict(color="rgba(150,150,150,0.6)", width=1.5, dash="dash"),
            layer="below",
        )
        fig.add_annotation(x=x_max * 0.02, y=sfl, text="SFL", showarrow=False, font=dict(color="#95a5a6", size=11))

    if wfl > 0 and wfl != sfl:
        fig.add_shape(
            type="line",
            x0=0,
            x1=x_max * 1.05,
            y0=wfl,
            y1=wfl,
            line=dict(color="rgba(230,126,34,0.6)", width=1.5, dash="dash"),
            layer="below",
        )

    title = f"Gas Lift Design — Pressure vs Depth"
    if case_label:
        title += f" ({case_label})"

    fig.update_layout(
        title=title,
        height=720,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=90, b=60),
        hovermode="closest",
        plot_bgcolor="rgba(30,30,30,0.25)",
    )
    fig.update_xaxes(
        title_text="Pressure (psi)",
        range=[0, x_max * 1.08],
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
    )
    fig.update_yaxes(
        autorange="reversed",
        title_text="True Vertical Depth TVD (ft)",
        range=[well_depth * 1.02, 0],
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
    )
    return fig
