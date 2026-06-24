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
    find_line_intersection,
)
from valve_engine import resolve_sfl


def _tubing_operating_pressure(p_so: float, g_u: float, valve_number: int, depth: float) -> float:
    p_so_n = operating_surface_pressure(p_so, valve_number)
    return p_so_n + g_u * depth


def _kill_fluid_gradient(case: dict, first_valve_depth: float, p_ko: float, g_s: float, g_u: float) -> float:
    """G_kill = P_ko(D1) / D1 — same gradient as the kill-fluid reference line."""
    if first_valve_depth <= 0:
        return g_u
    p_ko_at_first = casing_pressure_at_depth(first_valve_depth, p_ko, g_s, 1)
    return p_ko_at_first / first_valve_depth


def _casing_meets_tubing_depth(
    d_start: float,
    d_search_to: float,
    p_ko: float,
    g_casing: float,
    p_so: float,
    g_u: float,
    target_valve_num: int,
    step: float,
) -> tuple[float, float]:
    """
    Depth/pressure where Pc(D) = Pt(D) for the next operating tubing line.
    Falls back to the scheduled valve depth on the blue line when no crossing exists.
    """
    import numpy as np

    p_so_n = operating_surface_pressure(p_so, target_valve_num)
    depths = np.arange(d_start, d_search_to + step * 0.01, step)
    if depths.size == 0:
        depths = np.array([d_start, d_search_to])
    elif depths[-1] < d_search_to:
        depths = np.append(depths, d_search_to)

    casing_p = p_ko + g_casing * depths
    tubing_p = p_so_n + g_u * depths
    ix_d, ix_p = find_line_intersection(
        casing_p, tubing_p, depths, search_start_depth=d_start + 0.1, step=step
    )
    if ix_d is not None and ix_d > d_start:
        return float(ix_d), float(ix_p)
    p_at_target = p_so_n + g_u * d_search_to
    return float(d_search_to), float(p_at_target)


def build_valve_zigzag(case: dict, step: float = 10.0) -> tuple[list[float], list[float]]:
    """
    Continuous valve unloading path per UTM equations:
      1. Kill fluid from surface: P = G_kill × D
      2. At each valve: horizontal bridge ends on operating tubing (blue): Pt = P_so_n + G_u × D
      3. Casing gas diagonal: P = P_ko + G_s_adj × D until it meets the next blue tubing line
      4. After the last valve: follow the blue operating tubing line to the design limit
    """
    plot_depth = design_limit_from_case(case)
    p_ko = float(case.get("p_ko", 950.0))
    p_so = float(case.get("p_so", 900.0))
    g_s = float(case.get("g_s", 0.5))
    g_u = float(case.get("g_u", 0.125))
    valves = case.get("valve_depths", [])

    if not valves:
        return [], []

    import numpy as np

    xs: list[float] = []
    ys: list[float] = []
    d1 = float(valves[0])
    g_kill = _kill_fluid_gradient(case, d1, p_ko, g_s, g_u)

    def append_point(pressure: float, depth: float) -> None:
        xs.append(float(pressure))
        ys.append(float(depth))

    def break_before_casing_segment() -> None:
        """Break trace so gas injection (Pc jump) is not drawn past the blue line."""
        if xs and not (isinstance(xs[-1], float) and np.isnan(xs[-1])):
            xs.append(float("nan"))
            ys.append(float("nan"))

    def add_depth_line(d_start: float, d_end: float, pressure_fn) -> None:
        if d_end < d_start:
            return
        depths = np.arange(d_start, d_end + step * 0.01, step)
        if depths.size == 0 or depths[-1] < d_end:
            depths = np.append(depths, d_end)
        for j, d in enumerate(depths):
            p = float(pressure_fn(d))
            if (
                j == 0
                and xs
                and ys[-1] == d
                and abs(xs[-1] - p) < 0.5
                and not (isinstance(xs[-1], float) and np.isnan(xs[-1]))
            ):
                continue
            append_point(p, d)

    # Step 1 — kill fluid from surface to valve 1 (SFL)
    add_depth_line(0.0, d1, lambda d: g_kill * d)

    for i, d_v in enumerate(valves):
        valve_num = i + 1
        d_v = float(d_v)
        p_blue = _tubing_operating_pressure(p_so, g_u, valve_num, d_v)

        # Step 2 — horizontal bridge ends on the blue operating tubing line (valve 1 only)
        if i == 0:
            p_arrival = g_kill * d_v
            if abs(p_blue - p_arrival) > 0.5:
                append_point(p_blue, d_v)

        if i < len(valves) - 1:
            next_valve_num = valve_num + 1
            g_seg = casing_gradient_for_valve_number(g_s, next_valve_num)
            d_target = float(valves[i + 1])
            d_end, p_end = _casing_meets_tubing_depth(
                d_v,
                max(d_target, d_v + step),
                p_ko,
                g_seg,
                p_so,
                g_u,
                next_valve_num,
                step,
            )

            break_before_casing_segment()
            add_depth_line(d_v, d_end, lambda d, gs=g_seg: p_ko + gs * d)
            xs[-1] = p_end
            ys[-1] = d_end
        elif plot_depth > d_v:
            add_depth_line(
                d_v,
                plot_depth,
                lambda d, vn=valve_num: _tubing_operating_pressure(p_so, g_u, vn, d),
            )

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
