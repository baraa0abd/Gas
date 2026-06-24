"""Gas lift valve spacing engines — graphical intersection / IPO and analytical."""

from __future__ import annotations

from pressure_engines import (
    DEPTH_STEP_FT,
    calculate_casing_pressure_line,
    calculate_sfl,
    calculate_tubing_pressure_line,
    casing_gradient_for_valve_number,
    design_limit_from_case,
    find_line_intersection,
    ipo_spacing_depth,
    operating_surface_pressure,
)

MAX_VALVES = 12


def _extract_case(case: dict) -> dict:
    return {
        "well_depth": float(case.get("well_depth", 8000.0)),
        "p_wh": float(case.get("p_wh", 100.0)),
        "p_ko": float(case.get("p_ko", 950.0)),
        "p_so": float(case.get("p_so", 900.0)),
        "g_s": float(case.get("g_s", 0.5)),
        "g_u": float(case.get("g_u", 0.125)),
        "sfl_input": float(case.get("sfl", 0.0)),
    }


def resolve_sfl(case: dict) -> float:
    """Use provided SFL or calculate from static column."""
    params = _extract_case(case)
    if params["sfl_input"] > 0:
        return round(params["sfl_input"], 1)
    return round(
        calculate_sfl(params["well_depth"], params["p_wh"], params["g_u"]),
        1,
    )


def design_valve_spacing_graphical(case: dict) -> tuple[list[float], list[dict]]:
    """
    Graphical IPO method:
      - Valve 1 at SFL
      - Valves 2+ at Pc(D) = Pt(D) intersection, or IPO spacing when lines do not cross
    """
    p = _extract_case(case)
    well_depth = p["well_depth"]
    design_limit = design_limit_from_case(case)
    sfl = resolve_sfl(case)

    if sfl <= 0 or sfl > design_limit:
        return [], []

    valve_depths = [sfl]
    details: list[dict] = [
        {
            "valve_number": 1,
            "depth_ft": sfl,
            "method": "SFL (Valve 1)",
            "p_so_n": p["p_so"],
            "g_s_adj": p["g_s"],
        }
    ]

    for valve_num in range(2, MAX_VALVES + 1):
        prev_depth = valve_depths[-1]
        if prev_depth >= design_limit:
            break

        p_so_n = operating_surface_pressure(p["p_so"], valve_num)
        g_s_adj = casing_gradient_for_valve_number(p["g_s"], valve_num)

        _, casing_p = calculate_casing_pressure_line(
            p["p_ko"], p["g_s"], well_depth, valve_num
        )
        depths, tubing_p = calculate_tubing_pressure_line(
            p["p_so"], p["g_u"], well_depth, valve_num
        )

        ix_depth, ix_pressure = find_line_intersection(
            casing_p,
            tubing_p,
            depths,
            search_start_depth=prev_depth + 1.0,
        )

        ipo_depth = round(
            float(
                ipo_spacing_depth(
                    prev_depth,
                    p_so_n,
                    p["p_wh"],
                    p["g_u"],
                    p["g_s"],
                    valve_num,
                )
            ),
            1,
        )

        method = "IPO spacing (Pc = Pt equivalent)"
        depth_ix = ipo_depth

        if ix_depth is not None and ix_depth > prev_depth:
            p_c_ix = p["p_ko"] + g_s_adj * ix_depth
            p_t_ix = p_so_n + p["g_u"] * ix_depth
            if abs(p_c_ix - p_t_ix) < 5.0 and abs(ix_depth - ipo_depth) <= 100.0:
                depth_ix = round(float(ix_depth), 1)
                method = "Line intersection"

        if depth_ix <= prev_depth or depth_ix > design_limit:
            break

        if depth_ix - prev_depth < 200:
            break

        valve_depths.append(depth_ix)
        details.append(
            {
                "valve_number": valve_num,
                "depth_ft": depth_ix,
                "method": method,
                "p_so_n": p_so_n,
                "g_s_adj": round(g_s_adj, 4),
                "intersection_pressure_psi": ix_pressure,
            }
        )

    return valve_depths, details


def design_valve_spacing_analytical(case: dict) -> tuple[list[float], list[dict]]:
    """
    Analytical method:
      - Valve 1: DV_1 = P_ko / G_s
      - Valves 2+: ΔD = (P_so_n - G_u × D_prev - P_wh) / G_s
    """
    p = _extract_case(case)
    well_depth = p["well_depth"]

    if p["g_s"] <= 0:
        return [], []

    dv1 = p["p_ko"] / p["g_s"]
    if dv1 > well_depth:
        return [round(dv1, 1)], [{"valve_number": 1, "depth_ft": round(dv1, 1), "method": "P_ko/G_s"}]

    valve_depths = [round(dv1, 1)]
    details = [{"valve_number": 1, "depth_ft": valve_depths[0], "method": "P_ko/G_s"}]
    depth_current = dv1

    for valve_num in range(2, MAX_VALVES + 1):
        p_so_n = operating_surface_pressure(p["p_so"], valve_num)
        g_adj = casing_gradient_for_valve_number(p["g_s"], valve_num)
        delta = (p_so_n - p["g_u"] * depth_current - p["p_wh"]) / g_adj
        if delta <= 0:
            break
        depth_next = depth_current + delta
        if depth_next > well_depth:
            break
        depth_next = round(depth_next, 1)
        valve_depths.append(depth_next)
        details.append(
            {
                "valve_number": valve_num,
                "depth_ft": depth_next,
                "method": "Analytical spacing",
                "p_so_n": p_so_n,
                "delta_ft": round(delta, 1),
            }
        )
        depth_current = depth_next

    return valve_depths, details


def design_valves(case: dict) -> tuple[list[float], list[dict]]:
    method = case.get("method", "Analytical")
    if method == "Graphical":
        return design_valve_spacing_graphical(case)
    return design_valve_spacing_analytical(case)


def validate_valve_spacing(case: dict, valve_depths: list[float]) -> list[dict]:
    """Engineering validation checks on valve spacing."""
    results: list[dict] = []
    well_depth = float(case.get("well_depth", 5000.0))
    design_limit = design_limit_from_case(case)
    p_ko = float(case.get("p_ko", 900.0))
    p_so = float(case.get("p_so", 850.0))
    p_wh = float(case.get("p_wh", 200.0))
    g_s = float(case.get("g_s", 0.5))
    g_u = float(case.get("g_u", 0.15))

    if not valve_depths:
        results.append({"check": "valve_count", "severity": "warning", "message": "No valves calculated."})
        return results

    for i, depth in enumerate(valve_depths):
        if depth > design_limit:
            results.append(
                {
                    "check": "design_limit",
                    "severity": "error",
                    "message": f"Valve {i + 1} at {depth:.0f} ft exceeds design limit {design_limit:.0f} ft.",
                }
            )
        if i > 0:
            spacing = depth - valve_depths[i - 1]
            if spacing < 200:
                results.append(
                    {
                        "check": "min_spacing",
                        "severity": "warning",
                        "message": f"Valve {i + 1} spacing {spacing:.0f} ft < 200 ft minimum.",
                    }
                )
            if spacing > 1500:
                results.append(
                    {
                        "check": "max_spacing",
                        "severity": "warning",
                        "message": f"Valve {i + 1} spacing {spacing:.0f} ft > 1500 ft maximum.",
                    }
                )

        from pressure_engines import casing_pressure_at_depth, tubing_pressure_at_depth

        p_so_n = operating_surface_pressure(p_so, i + 1)
        p_c = casing_pressure_at_depth(depth, p_ko, g_s, i + 1)
        p_t = tubing_pressure_at_depth(depth, p_so_n, g_u)
        margin = p_c - p_t
        if margin < 50:
            results.append(
                {
                    "check": "pressure_margin",
                    "severity": "warning",
                    "message": f"Valve {i + 1} margin {margin:.0f} psi < 50 psi recommended.",
                }
            )

    method = case.get("method", "Analytical")
    if method == "Graphical":
        sfl = resolve_sfl(case)
        if abs(valve_depths[0] - sfl) > 1.0:
            results.append(
                {
                    "check": "sfl_valve1",
                    "severity": "warning",
                    "message": f"Valve 1 ({valve_depths[0]:.0f} ft) differs from SFL ({sfl:.0f} ft).",
                }
            )

    if not results:
        results.append({"check": "all", "severity": "ok", "message": "All validation checks passed."})
    return results
