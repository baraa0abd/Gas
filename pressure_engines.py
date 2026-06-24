"""Pressure line generation and intersection utilities for gas lift design."""

from __future__ import annotations

import numpy as np

DEPTH_STEP_FT = 25.0
GRADIENT_SHIFT_PER_VALVE = 0.022


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


def operating_surface_pressure(p_so: float, valve_number: int) -> float:
    """P_so_n = P_so - 25 × (n - 1)."""
    return p_so - 25.0 * max(valve_number - 1, 0)


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
) -> tuple[np.ndarray, np.ndarray]:
    """Operating tubing line: Pt(D) = P_so_n + G_u × D."""
    depths = depth_array(well_depth, step)
    p_so_n = operating_surface_pressure(p_so, valve_number)
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
) -> tuple[float, float]:
    """Return (P_casing, P_tubing) at a valve depth."""
    p_c = casing_pressure_at_depth(valve_depth, p_ko, g_s, valve_number)
    p_so_n = operating_surface_pressure(p_so, valve_number)
    p_t = tubing_pressure_at_depth(valve_depth, p_so_n, g_u)
    return round(p_c, 1), round(p_t, 1)
