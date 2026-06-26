"""Plotly pressure-depth diagram for gas lift design."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from pressure_engines import (
    calculate_casing_pressure_line,
    casing_gradient_for_valve_number,
    design_limit_from_case,
    find_line_intersection,
    kill_fluid_endpoints,
    operating_boundary_pressure,
    operating_surface_pressure,
    pob_intersection,
    pressures_at_valve,
    sfl_line_endpoints,
    unloading_surface_pressure,
    valve_type_from_case,
    wfl_depth,
    wfl_line_endpoints,
)
from valve_engine import resolve_sfl


def _casing_meets_boundary_depth(
    case: dict,
    d_start: float,
    d_search_to: float,
    p_ko: float,
    g_casing: float,
    target_valve_num: int,
    step: float,
) -> tuple[float, float]:
    """Depth/pressure where casing gas line meets the operating gas boundary."""
    p_so = float(case.get("p_so", 900.0))
    g_u = float(case.get("g_u", 0.125))
    g_s = float(case.get("g_s", 0.5))
    vtype = valve_type_from_case(case)

    depths = np.arange(d_start, d_search_to + step * 0.01, step)
    if depths.size == 0:
        depths = np.array([d_start, d_search_to])
    elif depths[-1] < d_search_to:
        depths = np.append(depths, d_search_to)

    casing_p = p_ko + g_casing * depths
    if vtype == "unbalanced":
        boundary_p = p_so + g_s * depths
    else:
        p_so_n = operating_surface_pressure(p_so, target_valve_num, vtype)
        boundary_p = p_so_n + g_u * depths

    ix_d, ix_p = find_line_intersection(
        casing_p, boundary_p, depths, search_start_depth=d_start + 0.1, step=step
    )
    if ix_d is not None and ix_d > d_start:
        return float(ix_d), float(ix_p)
    p_at_target = operating_boundary_pressure(case, target_valve_num, d_search_to)
    return float(d_search_to), float(p_at_target)


def _clip_two_point_line(
    p1: tuple[float, float],
    p2: tuple[float, float],
    plot_depth: float,
) -> tuple[list[float], list[float]]:
    """Clip a straight (P, D) segment to design-limit depth."""
    xs = [p1[0], p2[0]]
    ys = [p1[1], p2[1]]
    if max(ys) <= plot_depth:
        return xs, ys
    out_x, out_y = [], []
    for i in range(len(xs)):
        if ys[i] <= plot_depth:
            out_x.append(xs[i])
            out_y.append(ys[i])
        elif i > 0 and ys[i - 1] < plot_depth < ys[i]:
            frac = (plot_depth - ys[i - 1]) / (ys[i] - ys[i - 1])
            p_ix = xs[i - 1] + frac * (xs[i] - xs[i - 1])
            out_x.extend([p_ix, xs[i]])
            out_y.extend([plot_depth, ys[i]])
            break
    return out_x or xs[:1], out_y or ys[:1]


def build_valve_zigzag(case: dict, step: float = 10.0) -> tuple[list[float], list[float]]:
    """
    Valve unloading path:
      1. Kill fluid from (Psurface, 0) with gradient Gs to valve 1
      2. Horizontal bridge ends on operating gas boundary (blue / PSO)
      3. Casing diagonal until next boundary intersection
      4. After last valve: follow boundary line to design limit
    """
    plot_depth = design_limit_from_case(case)
    p_ko = float(case.get("p_ko", 950.0))
    p_so = float(case.get("p_so", 900.0))
    g_s = float(case.get("g_s", 0.5))
    g_u = float(case.get("g_u", 0.125))
    valves = case.get("valve_depths", [])

    if not valves:
        return [], []

    xs: list[float] = []
    ys: list[float] = []
    d1 = float(valves[0])
    p_surface = unloading_surface_pressure(case)

    def append_point(pressure: float, depth: float) -> None:
        xs.append(float(pressure))
        ys.append(float(depth))

    def break_before_casing_segment() -> None:
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

    # Kill fluid descent: P = Psurface + Gs × D
    add_depth_line(0.0, d1, lambda d: p_surface + g_s * d)

    for i, d_v in enumerate(valves):
        valve_num = i + 1
        d_v = float(d_v)
        p_boundary = operating_boundary_pressure(case, valve_num, d_v)

        # Horizontal bridge to operating gas boundary (valve 1; DV_2+ arrive via casing end)
        if i == 0:
            p_arrival = p_surface + g_s * d_v
            if abs(p_boundary - p_arrival) > 0.5:
                append_point(p_boundary, d_v)

        if i < len(valves) - 1:
            next_valve_num = valve_num + 1
            g_seg = casing_gradient_for_valve_number(g_s, next_valve_num)
            d_target = float(valves[i + 1])
            d_end, p_end = _casing_meets_boundary_depth(
                case,
                d_v,
                max(d_target, d_v + step),
                p_ko,
                g_seg,
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
                lambda d, vn=valve_num: operating_boundary_pressure(case, vn, d),
            )

    return xs, ys


def plot_pressure_depth_diagram(
    case: dict,
    case_label: str = "",
) -> go.Figure:
    """Build the gas lift pressure vs depth diagram per revised graphical spec."""
    well_depth = float(case.get("well_depth", 8000.0))
    plot_depth = design_limit_from_case(case)
    p_ko = float(case.get("p_ko", 950.0))
    p_so = float(case.get("p_so", 900.0))
    p_wh = float(case.get("p_wh", 100.0))
    g_s = float(case.get("g_s", 0.5))
    g_u = float(case.get("g_u", 0.125))
    valves = case.get("valve_depths", [])
    sfl = resolve_sfl(case)
    wfl = wfl_depth(case)
    vtype = valve_type_from_case(case)
    prefix = f"{case_label} — " if case_label else ""
    fig = go.Figure()

    # PKO line: P = P_ko + G_s × D
    d_c, p_c = calculate_casing_pressure_line(p_ko, g_s, plot_depth, valve_number=1)
    fig.add_trace(
        go.Scatter(
            x=p_c, y=d_c, mode="lines",
            name=f"{prefix}PKO (Casing)",
            line=dict(color="#c0392b", width=2.5),
            hovertemplate="PKO<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # PSO line: P = P_so + G_s × D
    d_pso, p_pso = calculate_casing_pressure_line(p_so, g_s, plot_depth, valve_number=1)
    fig.add_trace(
        go.Scatter(
            x=p_pso, y=d_pso, mode="lines",
            name=f"{prefix}PSO",
            line=dict(color="#e74c3c", width=2.0, dash="dot"),
            hovertemplate="PSO<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # Tubing line: (Pwh, 0) → POB (WFL ∩ PSO − 100 psi)
    d_pob, p_pob = pob_intersection(case)
    d_pob = min(d_pob, plot_depth)
    fig.add_trace(
        go.Scatter(
            x=[p_wh, p_pob], y=[0.0, d_pob], mode="lines",
            name=f"{prefix}Tubing (to POB)",
            line=dict(color="#2980b9", width=2.5),
            hovertemplate="Tubing<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # Kill fluid: (Psurface, 0) → (2000 psi, D2)
    k1, k2 = kill_fluid_endpoints(case)
    kx, ky = _clip_two_point_line(k1, k2, plot_depth)
    fig.add_trace(
        go.Scatter(
            x=kx, y=ky, mode="lines",
            name=f"{prefix}Kill Fluid",
            line=dict(color="#e67e22", width=2.0, dash="dash"),
            hovertemplate="Kill Fluid<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # SFL boundary: (Pwh, 0) → (0, SFL)
    s1, s2 = sfl_line_endpoints(case)
    sx, sy = _clip_two_point_line(s1, s2, plot_depth)
    fig.add_trace(
        go.Scatter(
            x=sx, y=sy, mode="lines",
            name=f"{prefix}SFL (Static boundary)",
            line=dict(color="#3498db", width=2.0, dash="solid"),
            hovertemplate="SFL<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # WFL boundary: (Pwh, 0) → (0, WFL)
    w1, w2 = wfl_line_endpoints(case)
    wx, wy = _clip_two_point_line(w1, w2, plot_depth)
    fig.add_trace(
        go.Scatter(
            x=wx, y=wy, mode="lines",
            name=f"{prefix}WFL (Working boundary)",
            line=dict(color="#d35400", width=2.0, dash="dot"),
            hovertemplate="WFL<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
        )
    )

    # Operating boundary lines per valve (balanced tubing / unbalanced uses PSO only once)
    max_n = max(len(valves), 4)
    for n in range(1, max_n + 1):
        if vtype == "unbalanced" and n > 1:
            break
        depths = np.arange(0, plot_depth + 1, 25)
        pressures = [operating_boundary_pressure(case, n, d) for d in depths]
        dash = "solid" if n == 1 else "dot"
        label = "PSO (Unbalanced valves)" if vtype == "unbalanced" else (
            f"Tubing Valve {n}" if n > 1 else "Tubing Valve 1 (Balanced)"
        )
        fig.add_trace(
            go.Scatter(
                x=pressures, y=depths, mode="lines",
                name=f"{prefix}{label}",
                line=dict(color="#5dade2" if n > 1 else "#2980b9", width=1.5, dash=dash),
                showlegend=(n <= 4),
                hovertemplate=f"{label}<br>P: %{{x:.1f}} psi<br>D: %{{y:.1f}} ft<extra></extra>",
            )
        )

    # Valve unloading zigzag
    zig_x, zig_y = build_valve_zigzag(case)
    if zig_x and zig_y:
        fig.add_trace(
            go.Scatter(
                x=zig_x, y=zig_y, mode="lines",
                name=f"{prefix}Valve Unloading Zigzag",
                line=dict(color="#27ae60", width=3.0),
                hovertemplate="Unloading path<br>P: %{x:.1f} psi<br>D: %{y:.1f} ft<extra></extra>",
            )
        )

    # Valve markers on operating boundary
    if valves:
        vx, vy, vlabels = [], [], []
        for i, d_v in enumerate(valves, start=1):
            _, p_b = pressures_at_valve(d_v, p_ko, p_so, p_wh, g_s, g_u, i, vtype)
            vx.append(p_b)
            vy.append(d_v)
            vlabels.append(f"V{i}")
        fig.add_trace(
            go.Scatter(
                x=vx, y=vy, mode="markers+text",
                name=f"{prefix}Valves",
                marker=dict(size=11, color="#1e8449", symbol="circle", line=dict(width=1.5, color="#fff")),
                text=vlabels, textposition="middle right",
                textfont=dict(size=10, color="#1e8449"),
                hovertemplate="Valve<br>P: %{x:.1f} psi<br>Depth: %{y:.1f} ft<extra></extra>",
            )
        )

    x_max = max(float(max(p_c)), float(max(p_pso)), float(p_pob), 500.0)

    # Design limit marker
    fig.add_shape(
        type="line", x0=0, x1=x_max * 1.05, y0=plot_depth, y1=plot_depth,
        line=dict(color="rgba(230, 126, 34, 0.85)", width=2, dash="dash"), layer="below",
    )
    fig.add_annotation(
        x=x_max * 0.02, y=plot_depth,
        text=f"Design Limit ({plot_depth:,.0f} ft)",
        showarrow=False, font=dict(color="#e67e22", size=11),
    )

    for d_v in valves:
        fig.add_shape(
            type="line", x0=0, x1=x_max * 1.05, y0=d_v, y1=d_v,
            line=dict(color="rgba(120, 120, 120, 0.45)", width=1, dash="dash"), layer="below",
        )

    if sfl > 0:
        fig.add_annotation(x=x_max * 0.02, y=sfl, text="SFL", showarrow=False, font=dict(color="#3498db", size=11))
    if wfl > 0:
        fig.add_annotation(x=x_max * 0.02, y=wfl, text="WFL", showarrow=False, font=dict(color="#d35400", size=11))

    title = "Gas Lift Design — Pressure vs Depth"
    if case_label:
        title += f" ({case_label})"

    fig.update_layout(
        title=title, height=720,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=90, b=60),
        hovermode="closest",
        plot_bgcolor="rgba(30,30,30,0.25)",
    )
    fig.update_xaxes(title_text="Pressure (psi)", range=[0, x_max * 1.08], showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    fig.update_yaxes(
        autorange="reversed", title_text="True Vertical Depth TVD (ft)",
        range=[well_depth * 1.02, 0], showgrid=True, gridcolor="rgba(255,255,255,0.08)",
    )
    return fig
