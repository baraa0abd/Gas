"""Pressure line generation and intersection utilities for gas lift design."""

from __future__ import annotations

import numpy as np

DEPTH_STEP_FT = 25.0
GRADIENT_SHIFT_PER_VALVE = 0.022
DEFAULT_DESIGN_LIMIT_FT = 5550.0
KILL_FLUID_ANCHOR_PSI = 2000.0
POB_OFFSET_PSI = 100.0


def unloading_surface_pressure(case: dict) -> float:
    """Psurface for kill-fluid start based on unloading destination."""
    dest = str(case.get("unloading_destination", "surface")).lower()
    if dest == "separator":
        return float(case.get("separator_pressure_psi", case.get("p_sep", 100.0)))
    if dest == "surface":
        return float(case.get("p_wh", 100.0))
    return 0.0


def static_sfl_depth(case: dict) -> float:
    """SFL depth at Pr=0: SFL = WD − Ps / Gs."""
    if float(case.get("sfl", 0.0)) > 0:
        return float(case["sfl"])
    well_depth = float(case.get("well_depth", 8000.0))
    g_s = float(case.get("g_s", 0.5))
    if g_s <= 0:
        return 0.0
    ps = unloading_surface_pressure(case)
    return max(well_depth - ps / g_s, 0.0)


def wfl_depth(case: dict) -> float:
    """WFL depth at Pr=0: WFL = WD − Pwf / Gfb, Gfb = Gs."""
    well_depth = float(case.get("well_depth", 8000.0))
    g_s = float(case.get("g_s", 0.5))
    pwf = float(case.get("pwf", case.get("p_wh", 100.0)))
    if g_s <= 0:
        return 0.0
    return max(well_depth - pwf / g_s, 0.0)


def wfl_pressure_at_depth(depth: float, p_wh: float, wfl_d: float) -> float:
    """WFL line from (Pwh, 0) to (0, WFL)."""
    if wfl_d <= 0:
        return p_wh
    return p_wh * (1.0 - depth / wfl_d)


def sfl_line_endpoints(case: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """SFL boundary: (Pwh, 0) → (0, SFL)."""
    p_wh = float(case.get("p_wh", 100.0))
    return (p_wh, 0.0), (0.0, static_sfl_depth(case))


def wfl_line_endpoints(case: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """WFL boundary: (Pwh, 0) → (0, WFL)."""
    p_wh = float(case.get("p_wh", 100.0))
    return (p_wh, 0.0), (0.0, wfl_depth(case))


def pob_intersection(case: dict) -> tuple[float, float]:
    """POB point: intersection of WFL and PSO lines, minus 100 psi."""
    p_wh = float(case.get("p_wh", 100.0))
    p_so = float(case.get("p_so", 900.0))
    g_s = float(case.get("g_s", 0.5))
    wfl_d = wfl_depth(case)
    if wfl_d <= 0:
        return 0.0, max(p_wh - POB_OFFSET_PSI, 0.0)
    denom = p_wh / wfl_d + g_s
    if abs(denom) < 1e-9:
        return 0.0, max(p_wh - POB_OFFSET_PSI, 0.0)
    d_ix = max((p_wh - p_so) / denom, 0.0)
    p_ix = wfl_pressure_at_depth(d_ix, p_wh, wfl_d)
    return float(d_ix), float(p_ix - POB_OFFSET_PSI)


def kill_fluid_endpoints(case: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """Kill fluid: (Psurface, 0) → (2000 psi, D2) with D2 = (2000 − Psurface) / Gs."""
    p_surface = unloading_surface_pressure(case)
    g_s = float(case.get("g_s", 0.5))
    anchor = float(case.get("kill_fluid_anchor_psi", KILL_FLUID_ANCHOR_PSI))
    if g_s <= 0:
        g_s = 0.5
    d2 = (anchor - p_surface) / g_s
    return (p_surface, 0.0), (anchor, max(d2, 0.0))


def valve_type_from_case(case: dict) -> str:
    return str(case.get("valve_type", "balanced")).lower()


def is_unbalanced(case: dict) -> bool:
    return valve_type_from_case(case) == "unbalanced"


def plotting_depth(well_depth: float, design_limit_depth: float) -> float:
    """Maximum depth shown on pressure-depth diagrams."""
    return min(float(well_depth), float(design_limit_depth))


def design_limit_from_case(case: dict) -> float:
    """Resolve effective design limit for a case (capped by well depth)."""
    well_depth = float(case.get("well_depth", 8000.0))
    limit = float(case.get("design_limit_depth", case.get("design_limit", DEFAULT_DESIGN_LIMIT_FT)))
    return plotting_depth(well_depth, limit)


def depth_array(well_depth: float, step: float = DEPTH_STEP_FT) -> np.ndarray:
    depths = np.arange(0.0, well_depth + step * 0.01, step)
    if depths.size == 0 or depths[-1] != well_depth:
        depths = np.append(depths, well_depth)
    return depths


def adjusted_gas_gradient(g_s: float, valves_already_installed: int) -> float:
    """G_s reduced by 0.022 psi/ft for each valve already in the well."""
    return g_s - GRADIENT_SHIFT_PER_VALVE * max(valves_already_installed, 0)


def casing_gradient_for_valve_number(g_s: float, valve_number: int) -> float:
    """Gradient when placing/searching for valve n (n-1 valves already installed)."""
    return adjusted_gas_gradient(g_s, max(valve_number - 1, 0))


def operating_surface_pressure(
    p_so: float,
    valve_number: int,
    valve_type: str = "balanced",
) -> float:
    """Balanced: P_so − 25×(n−1). Unbalanced: strict P_so."""
    if str(valve_type).lower() == "unbalanced":
        return p_so
    return p_so - 25.0 * max(valve_number - 1, 0)


def operating_boundary_pressure(case: dict, valve_number: int, depth: float) -> float:
    """
    Operating gas boundary at depth D.
    Balanced: Pt = P_so_n + G_u × D (tubing operating line).
    Unbalanced: valves on strict PSO casing line, P = P_so + G_s × D.
    """
    p_so = float(case.get("p_so", 900.0))
    g_u = float(case.get("g_u", 0.125))
    g_s = float(case.get("g_s", 0.5))
    vtype = valve_type_from_case(case)
    if vtype == "unbalanced":
        return p_so + g_s * depth
    p_so_n = operating_surface_pressure(p_so, valve_number, vtype)
    return p_so_n + g_u * depth


def casing_pressure_at_depth(
    depth: float,
    p_ko: float,
    g_s: float,
    valve_number: int = 1,
) -> float:
    """Pc(D) = P_ko + G_s_adjusted × D."""
    g_adj = casing_gradient_for_valve_number(g_s, valve_number)
    return p_ko + g_adj * depth


def tubing_pressure_at_depth(
    depth: float,
    p_surface: float,
    g_u: float,
) -> float:
    """Pt(D) = P_surface + G_u × D."""
    return p_surface + g_u * depth


def calculate_casing_pressure_line(
    p_ko: float,
    g_s: float,
    well_depth: float,
    valve_number: int = 1,
    step: float = DEPTH_STEP_FT,
) -> tuple[np.ndarray, np.ndarray]:
    depths = depth_array(well_depth, step)
    g_adj = casing_gradient_for_valve_number(g_s, valve_number)
    pressures = p_ko + g_adj * depths
    return depths, pressures


def calculate_tubing_pressure_line(
    p_so: float,
    g_u: float,
    well_depth: float,
    valve_number: int = 1,
    step: float = DEPTH_STEP_FT,
    valve_type: str = "balanced",
) -> tuple[np.ndarray, np.ndarray]:
    """Operating tubing line: Pt(D) = P_so_n + G_u × D."""
    depths = depth_array(well_depth, step)
    p_so_n = operating_surface_pressure(p_so, valve_number, valve_type)
    pressures = p_so_n + g_u * depths
    return depths, pressures


def calculate_kill_fluid_line(
    g_kill: float,
    well_depth: float,
    p_surface: float = 0.0,
    step: float = DEPTH_STEP_FT,
) -> tuple[np.ndarray, np.ndarray]:
    """Kill fluid line from surface static pressure."""
    depths = depth_array(well_depth, step)
    pressures = p_surface + g_kill * depths
    return depths, pressures


def calculate_sfl(
    well_depth: float,
    p_surface: float,
    g_kill: float,
) -> float:
    """SFL = D_well - (P_surface / G_kill)."""
    if g_kill <= 0:
        return 0.0
    return max(well_depth - (p_surface / g_kill), 0.0)


def find_line_intersection(
    casing_pressures: np.ndarray,
    tubing_pressures: np.ndarray,
    depths: np.ndarray,
    search_start_depth: float = 0.0,
    step: float = DEPTH_STEP_FT,
) -> tuple[float | None, float | None]:
    """
    Find depth where Pc(D) = Pt(D) by sign-change detection + linear interpolation.
    Returns (intersection_depth, intersection_pressure).
    """
    if len(depths) < 2:
        return None, None

    start_idx = int(np.searchsorted(depths, search_start_depth, side="left"))
    if start_idx >= len(depths) - 1:
        return None, None

    diff = casing_pressures - tubing_pressures
    for i in range(start_idx, len(depths) - 1):
        d0, d1 = depths[i], depths[i + 1]
        f0, f1 = diff[i], diff[i + 1]
        if f0 == 0:
            return round(float(d0), 1), round(float(casing_pressures[i]), 1)
        if f0 * f1 <= 0 and f1 != f0:
            frac = f0 / (f0 - f1)
            depth_ix = d0 + frac * (d1 - d0)
            pressure_ix = casing_pressures[i] + frac * (
                casing_pressures[i + 1] - casing_pressures[i]
            )
            return round(float(depth_ix), 1), round(float(pressure_ix), 1)
    return None, None


def ipo_spacing_depth(
    previous_depth: float,
    p_so_n: float,
    p_wh: float,
    g_u: float,
    g_s: float,
    valve_number: int,
) -> float:
    """
    IPO spacing: ΔD = (P_so_n - G_u × D_prev - P_wh) / G_s_adjusted
    G_s_adjusted uses (valve_number - 1) valves already installed.
    """
    g_adj = casing_gradient_for_valve_number(g_s, valve_number)
    if g_adj <= 0:
        return previous_depth
    return previous_depth + (p_so_n - g_u * previous_depth - p_wh) / g_adj


def pressures_at_valve(
    valve_depth: float,
    p_ko: float,
    p_so: float,
    p_wh: float,
    g_s: float,
    g_u: float,
    valve_number: int,
    valve_type: str = "balanced",
) -> tuple[float, float]:
    """Return (P_casing, P_boundary) at a valve depth."""
    p_c = casing_pressure_at_depth(valve_depth, p_ko, g_s, valve_number)
    if str(valve_type).lower() == "unbalanced":
        p_b = p_so + g_s * valve_depth
    else:
        p_so_n = operating_surface_pressure(p_so, valve_number, valve_type)
        p_b = tubing_pressure_at_depth(valve_depth, p_so_n, g_u)
    return round(p_c, 1), round(p_b, 1)
