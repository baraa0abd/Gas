"""
Separator sizing engine — Chapter 4 Separator Part 3 correlations
(Dr. Abdul Rahim Risal, UTM).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

R_GAS = 10.73  # psia·ft³/(lb·mol·°R)
M_AIR = 29.0
BBL_PER_FT3 = 1 / 5.615
IN_PER_FT = 12.0

SeparatorType = Literal["vertical", "horizontal"]
PhaseMode = Literal["2-phase", "3-phase"]


@dataclass
class FluidProperties:
    api_gravity: float
    sg_gas: float
    sg_water: float = 1.0
    pressure_psia: float = 100.0
    temperature_f: float = 60.0
    z_factor: float = 0.9

    @property
    def sg_oil(self) -> float:
        return 141.5 / (self.api_gravity + 131.5)

    @property
    def rho_oil(self) -> float:
        return self.sg_oil * 62.4

    @property
    def rho_water(self) -> float:
        return self.sg_water * 62.4

    @property
    def rho_gas(self) -> float:
        t_rankine = self.temperature_f + 460.0
        m_gas = self.sg_gas * M_AIR
        return (self.pressure_psia * m_gas) / (self.z_factor * R_GAS * t_rankine)

    @property
    def rho_liquid(self) -> float:
        return self.rho_oil


@dataclass
class FlowRates:
    gas_mmscfd: float
    oil_bopd: float
    water_bpd: float = 0.0


@dataclass
class RetentionSettings:
    oil_minutes: float
    water_minutes: float | None = None
    custom: bool = False


@dataclass
class DesignInputs:
    separator_type: SeparatorType
    phase_mode: PhaseMode
    fluids: FluidProperties
    flows: FlowRates
    retention: RetentionSettings
    k_factor: float
    shell_height_ft: float = 10.0
    liquid_fraction: float = 0.5
    ld_ratio_target: float = 4.0
    ld_ratio_min: float = 3.0
    ld_ratio_max: float = 5.0


@dataclass
class ConstraintResult:
    name: str
    governing: bool
    diameter_ft: float
    length_or_height_ft: float
    capacity_value: float
    capacity_unit: str
    formula: str


@dataclass
class SizingResult:
    separator_type: SeparatorType
    phase_mode: PhaseMode
    diameter_ft: float
    diameter_in: float
    length_ft: float
    liquid_height_ft: float
    ld_ratio: float
    governing_constraint: str
    constraints: list[ConstraintResult] = field(default_factory=list)
    fluid_summary: dict = field(default_factory=dict)
    retention_summary: dict = field(default_factory=dict)
    curve_data: list[dict] = field(default_factory=list)


def recommend_retention_minutes(
    phase_mode: PhaseMode,
    pressure_psia: float,
    temperature_f: float,
) -> tuple[float, float | None, str]:
    """Return (oil_min, water_min, note) based on lecture slide 8 rules."""
    if phase_mode == "2-phase":
        return 1.0, None, "Oil-gas separation: 1 min (rule of thumb)"

    if pressure_psia >= 500:
        return 3.5, 3.5, "Oil-gas-water high pressure: 2–5 min (midpoint used)"

    if temperature_f >= 100:
        oil_lo, oil_hi = 5.0, 10.0
    elif temperature_f >= 90:
        oil_lo, oil_hi = 10.0, 15.0
    elif temperature_f >= 80:
        oil_lo, oil_hi = 15.0, 20.0
    elif temperature_f >= 70:
        oil_lo, oil_hi = 20.0, 25.0
    else:
        oil_lo, oil_hi = 25.0, 30.0

    oil_mid = (oil_lo + oil_hi) / 2.0
    note = f"Low-pressure 3-phase @ {temperature_f:.0f}°F: {oil_lo:.0f}–{oil_hi:.0f} min"
    return oil_mid, oil_mid, note


def vertical_liquid_height(shell_height_ft: float) -> float:
    """Height of shell to liquid height ratio (slide 10 lookup, linear interpolation)."""
    table = {5.0: 2.5, 10.0: 3.25, 15.0: 4.25}
    keys = sorted(table)
    if shell_height_ft <= keys[0]:
        return table[keys[0]]
    if shell_height_ft >= keys[-1]:
        return table[keys[-1]]
    for lo, hi in zip(keys, keys[1:]):
        if lo <= shell_height_ft <= hi:
            frac = (shell_height_ft - lo) / (hi - lo)
            return table[lo] + frac * (table[hi] - table[lo])
    return table[10.0]


def gas_density_correction(fluids: FluidProperties, sg_gas: float | None = None) -> float:
    sg = sg_gas if sg_gas is not None else fluids.sg_gas
    t_rankine = fluids.temperature_f + 460.0
    return (fluids.pressure_psia * fluids.z_factor) / (t_rankine * sg)


def souders_brown_term(rho_liq: float, rho_gas: float) -> float:
    if rho_gas <= 0 or rho_liq <= rho_gas:
        return 0.0
    return math.sqrt((rho_liq - rho_gas) / rho_gas)


def vertical_gas_capacity_mmscfd(
    diameter_in: float,
    k_factor: float,
    fluids: FluidProperties,
    rho_liq: float | None = None,
) -> float:
    """D in inches (UTM correlation coefficient 0.0119)."""
    rho_l = rho_liq if rho_liq is not None else fluids.rho_liquid
    sb = souders_brown_term(rho_l, fluids.rho_gas)
    correction = gas_density_correction(fluids)
    return 0.0119 * k_factor * (diameter_in**2) * sb * correction


def vertical_oil_capacity_bopd(
    diameter_in: float,
    h_ft: float,
    sg_oil: float,
    retention_min: float,
) -> float:
    if retention_min <= 0:
        return float("inf")
    return (h_ft * (diameter_in**2) * sg_oil) / (0.12 * retention_min)


def vertical_diameter_from_gas(
    gas_mmscfd: float,
    k_factor: float,
    fluids: FluidProperties,
    rho_liq: float | None = None,
) -> float:
    """Return required diameter in inches."""
    rho_l = rho_liq if rho_liq is not None else fluids.rho_liquid
    sb = souders_brown_term(rho_l, fluids.rho_gas)
    correction = gas_density_correction(fluids)
    denom = 0.0119 * k_factor * sb * correction
    if denom <= 0 or gas_mmscfd <= 0:
        return 0.0
    return math.sqrt(gas_mmscfd / denom)


def vertical_diameter_from_oil(
    oil_bopd: float,
    h_ft: float,
    sg_oil: float,
    retention_min: float,
) -> float:
    """Return required diameter in inches."""
    if oil_bopd <= 0 or h_ft <= 0 or retention_min <= 0:
        return 0.0
    return math.sqrt((0.12 * retention_min * oil_bopd) / (h_ft * sg_oil))


def horizontal_gas_capacity_mmscfd(
    diameter_in: float,
    length_ft: float,
    k_factor: float,
    fluids: FluidProperties,
    liquid_fraction: float = 0.5,
    rho_liq: float | None = None,
) -> float:
    """D in inches, L in ft (d·Leff correlation)."""
    rho_l = rho_liq if rho_liq is not None else fluids.rho_liquid
    sb = souders_brown_term(rho_l, fluids.rho_gas)
    correction = gas_density_correction(fluids)
    f_vapor = max(0.1, 1.0 - liquid_fraction)
    return 0.0119 * k_factor * diameter_in * length_ft * sb * correction * f_vapor


def horizontal_oil_capacity_bopd(
    diameter_in: float,
    length_ft: float,
    sg_oil: float,
    retention_min: float,
    liquid_fraction: float = 0.5,
) -> float:
    if retention_min <= 0:
        return float("inf")
    return (diameter_in**2 * length_ft * sg_oil * liquid_fraction) / (0.1 * retention_min)


def horizontal_water_capacity_bpd(
    diameter_in: float,
    length_ft: float,
    sg_water: float,
    retention_min: float,
    water_fraction: float = 0.5,
) -> float:
    if retention_min <= 0:
        return float("inf")
    return (diameter_in**2 * length_ft * sg_water * water_fraction) / (0.1 * retention_min)


def round_up_standard_diameter_inches(diameter_in: float) -> float:
    standard = [12, 16, 20, 24, 30, 36, 42, 48, 60, 72, 84, 96]
    for size in standard:
        if diameter_in <= size:
            return float(size)
    return math.ceil(diameter_in / 12.0) * 12.0


def size_vertical(inputs: DesignInputs) -> SizingResult:
    fluids = inputs.fluids
    h_liq = vertical_liquid_height(inputs.shell_height_ft)
    rho_liq = fluids.rho_liquid

    d_gas_in = vertical_diameter_from_gas(inputs.flows.gas_mmscfd, inputs.k_factor, fluids, rho_liq)
    d_oil_in = vertical_diameter_from_oil(
        inputs.flows.oil_bopd, h_liq, fluids.sg_oil, inputs.retention.oil_minutes
    )
    d_water_in = 0.0
    if inputs.phase_mode == "3-phase" and inputs.flows.water_bpd > 0:
        water_ret = inputs.retention.water_minutes or inputs.retention.oil_minutes
        d_water_in = vertical_diameter_from_oil(
            inputs.flows.water_bpd, h_liq * 0.5, fluids.sg_water, water_ret
        )

    d_design_in = max(d_gas_in, d_oil_in, d_water_in)
    d_in = round_up_standard_diameter_inches(d_design_in)
    d_ft = d_in / IN_PER_FT

    gas_cap = vertical_gas_capacity_mmscfd(d_in, inputs.k_factor, fluids, rho_liq)
    oil_cap = vertical_oil_capacity_bopd(d_in, h_liq, fluids.sg_oil, inputs.retention.oil_minutes)
    water_cap = None
    if inputs.phase_mode == "3-phase":
        water_ret = inputs.retention.water_minutes or inputs.retention.oil_minutes
        water_cap = vertical_oil_capacity_bopd(d_in, h_liq * 0.5, fluids.sg_water, water_ret)

    constraints = [
        ConstraintResult(
            name="Gas capacity",
            governing=False,
            diameter_ft=d_gas_in / IN_PER_FT,
            length_or_height_ft=inputs.shell_height_ft,
            capacity_value=gas_cap,
            capacity_unit="MMscfd",
            formula="Q = 0.0119·K·D²·√((ρₗ−ρg)/ρg)·(P·Z)/(T·SG)",
        ),
        ConstraintResult(
            name="Oil retention",
            governing=False,
            diameter_ft=d_oil_in / IN_PER_FT,
            length_or_height_ft=h_liq,
            capacity_value=oil_cap,
            capacity_unit="BOPD",
            formula="q = (h·D²·SG)/ (0.12·t_r)",
        ),
    ]
    if inputs.phase_mode == "3-phase" and d_water_in > 0:
        constraints.append(
            ConstraintResult(
                name="Water retention",
                governing=False,
                diameter_ft=d_water_in / IN_PER_FT,
                length_or_height_ft=h_liq * 0.5,
                capacity_value=water_cap or 0.0,
                capacity_unit="BPD",
                formula="q = (h·D²·SG)/ (0.12·t_r)",
            )
        )

    diameters_in = {
        "Gas capacity": d_gas_in,
        "Oil retention": d_oil_in,
        "Water retention": d_water_in,
    }
    governing = max(diameters_in, key=diameters_in.get)
    for c in constraints:
        c.governing = c.name == governing

    curve = []
    for d_in_c in [12, 16, 20, 24, 30, 36, 42, 48, 60]:
        curve.append(
            {
                "diameter_in": d_in_c,
                "gas_capacity_mmscfd": round(vertical_gas_capacity_mmscfd(d_in_c, inputs.k_factor, fluids, rho_liq), 3),
                "oil_capacity_bopd": round(
                    vertical_oil_capacity_bopd(d_in_c, h_liq, fluids.sg_oil, inputs.retention.oil_minutes), 1
                ),
                "required_gas_mmscfd": inputs.flows.gas_mmscfd,
                "required_oil_bopd": inputs.flows.oil_bopd,
            }
        )

    return SizingResult(
        separator_type="vertical",
        phase_mode=inputs.phase_mode,
        diameter_ft=d_ft,
        diameter_in=d_in,
        length_ft=inputs.shell_height_ft,
        liquid_height_ft=h_liq,
        ld_ratio=inputs.shell_height_ft / d_ft if d_ft else 0.0,
        governing_constraint=governing,
        constraints=constraints,
        fluid_summary={
            "sg_oil": round(fluids.sg_oil, 4),
            "rho_oil_lbft3": round(fluids.rho_oil, 3),
            "rho_gas_lbft3": round(fluids.rho_gas, 5),
            "rho_water_lbft3": round(fluids.rho_water, 3),
        },
        retention_summary={
            "oil_minutes": inputs.retention.oil_minutes,
            "water_minutes": inputs.retention.water_minutes,
            "liquid_height_ft": h_liq,
        },
        curve_data=curve,
    )


def horizontal_length_from_gas(
    diameter_in: float,
    gas_mmscfd: float,
    k_factor: float,
    fluids: FluidProperties,
    liquid_fraction: float,
    rho_liq: float | None = None,
) -> float:
    rho_l = rho_liq if rho_liq is not None else fluids.rho_liquid
    sb = souders_brown_term(rho_l, fluids.rho_gas)
    correction = gas_density_correction(fluids)
    f_vapor = max(0.1, 1.0 - liquid_fraction)
    denom = 0.0119 * k_factor * diameter_in * sb * correction * f_vapor
    if denom <= 0 or gas_mmscfd <= 0:
        return 0.0
    return gas_mmscfd / denom


def size_horizontal(inputs: DesignInputs) -> SizingResult:
    fluids = inputs.fluids
    f_liq = inputs.liquid_fraction
    rho_liq = fluids.rho_liquid

    best: SizingResult | None = None

    for d_in in [12, 16, 20, 24, 30, 36, 42, 48, 60, 72]:
        l_gas = horizontal_length_from_gas(
            d_in, inputs.flows.gas_mmscfd, inputs.k_factor, fluids, f_liq, rho_liq
        )
        d_ft = d_in / IN_PER_FT
        l_oil = (
            (0.1 * inputs.retention.oil_minutes * inputs.flows.oil_bopd)
            / max(d_in**2 * fluids.sg_oil * f_liq, 1e-9)
            if inputs.flows.oil_bopd > 0
            else 0.0
        )
        l_water = 0.0
        water_ret = inputs.retention.water_minutes or inputs.retention.oil_minutes
        if inputs.phase_mode == "3-phase" and inputs.flows.water_bpd > 0:
            l_water = (0.1 * water_ret * inputs.flows.water_bpd) / max(
                d_in**2 * fluids.sg_water * f_liq * 0.5, 1e-9
            )

        l_design = max(l_gas, l_oil, l_water, d_ft * inputs.ld_ratio_min)
        ld = l_design / d_ft

        if ld > inputs.ld_ratio_max:
            continue

        gas_cap = horizontal_gas_capacity_mmscfd(d_in, l_design, inputs.k_factor, fluids, f_liq, rho_liq)
        oil_cap = horizontal_oil_capacity_bopd(d_in, l_design, fluids.sg_oil, inputs.retention.oil_minutes, f_liq)
        lengths = {"Gas capacity": l_gas, "Oil retention": l_oil, "Water retention": l_water}
        governing = max(lengths, key=lengths.get)

        constraints = [
            ConstraintResult(
                name="Gas capacity",
                governing=governing == "Gas capacity",
                diameter_ft=d_ft,
                length_or_height_ft=l_gas,
                capacity_value=gas_cap,
                capacity_unit="MMscfd",
                formula="Q = 0.0119·K·D·L·√((ρₗ−ρg)/ρg)·(P·Z)/(T·SG)·f_vapor",
            ),
            ConstraintResult(
                name="Oil retention",
                governing=governing == "Oil retention",
                diameter_ft=d_ft,
                length_or_height_ft=l_oil,
                capacity_value=oil_cap,
                capacity_unit="BOPD",
                formula="q = (D²·L·SG·f_liq)/(0.1·t_r)",
            ),
        ]
        if l_water > 0:
            w_cap = horizontal_water_capacity_bpd(d_in, l_design, fluids.sg_water, water_ret, f_liq * 0.5)
            constraints.append(
                ConstraintResult(
                    name="Water retention",
                    governing=governing == "Water retention",
                    diameter_ft=d_ft,
                    length_or_height_ft=l_water,
                    capacity_value=w_cap,
                    capacity_unit="BPD",
                    formula="q = (D²·L·SG·f_water)/(0.1·t_r)",
                )
            )

        if best is None or d_in < best.diameter_in or (d_in == best.diameter_in and l_design < best.length_ft):
            best = SizingResult(
                separator_type="horizontal",
                phase_mode=inputs.phase_mode,
                diameter_ft=d_ft,
                diameter_in=float(d_in),
                length_ft=round(l_design, 2),
                liquid_height_ft=d_ft * f_liq,
                ld_ratio=round(ld, 2),
                governing_constraint=governing,
                constraints=constraints,
                fluid_summary={
                    "sg_oil": round(fluids.sg_oil, 4),
                    "rho_oil_lbft3": round(fluids.rho_oil, 3),
                    "rho_gas_lbft3": round(fluids.rho_gas, 5),
                    "rho_water_lbft3": round(fluids.rho_water, 3),
                },
                retention_summary={
                    "oil_minutes": inputs.retention.oil_minutes,
                    "water_minutes": inputs.retention.water_minutes,
                    "liquid_fraction": f_liq,
                },
                curve_data=[],
            )

    if best is None:
        d_in = 60.0
        d_ft = d_in / IN_PER_FT
        l_design = d_ft * inputs.ld_ratio_max
        best = SizingResult(
            separator_type="horizontal",
            phase_mode=inputs.phase_mode,
            diameter_ft=d_ft,
            diameter_in=d_in,
            length_ft=l_design,
            liquid_height_ft=d_ft * f_liq,
            ld_ratio=inputs.ld_ratio_max,
            governing_constraint="Slenderness limit — manual review required",
            constraints=[],
            fluid_summary={
                "sg_oil": round(fluids.sg_oil, 4),
                "rho_oil_lbft3": round(fluids.rho_oil, 3),
                "rho_gas_lbft3": round(fluids.rho_gas, 5),
            },
            retention_summary={"oil_minutes": inputs.retention.oil_minutes},
            curve_data=[],
        )

    curve = []
    d_sel = best.diameter_in
    d_ft_sel = d_sel / IN_PER_FT
    for l_ft in [3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20]:
        if l_ft < d_ft_sel * inputs.ld_ratio_min:
            continue
        curve.append(
            {
                "length_ft": l_ft,
                "gas_capacity_mmscfd": round(
                    horizontal_gas_capacity_mmscfd(d_sel, l_ft, inputs.k_factor, fluids, f_liq, rho_liq), 3
                ),
                "oil_capacity_bopd": round(
                    horizontal_oil_capacity_bopd(d_sel, l_ft, fluids.sg_oil, inputs.retention.oil_minutes, f_liq),
                    1,
                ),
                "required_gas_mmscfd": inputs.flows.gas_mmscfd,
                "required_oil_bopd": inputs.flows.oil_bopd,
            }
        )
    best.curve_data = curve
    return best


def run_sizing(payload: dict) -> dict:
    phase_mode: PhaseMode = payload.get("phase_mode", "2-phase")
    separator_type: SeparatorType = payload.get("separator_type", "vertical")

    fluids = FluidProperties(
        api_gravity=float(payload.get("api_gravity", 35)),
        sg_gas=float(payload.get("sg_gas", 0.65)),
        sg_water=float(payload.get("sg_water", 1.0)),
        pressure_psia=float(payload.get("pressure_psia", 100)),
        temperature_f=float(payload.get("temperature_f", 60)),
        z_factor=float(payload.get("z_factor", 0.9)),
    )

    flows = FlowRates(
        gas_mmscfd=float(payload.get("gas_mmscfd", 5)),
        oil_bopd=float(payload.get("oil_bopd", 1000)),
        water_bpd=float(payload.get("water_bpd", 0)),
    )

    use_custom_retention = bool(payload.get("custom_retention", False))
    if use_custom_retention:
        oil_min = float(payload.get("retention_oil_min", 1))
        water_min = payload.get("retention_water_min")
        water_min = float(water_min) if water_min is not None else None
        ret_note = "User-specified retention time"
    else:
        oil_min, water_min, ret_note = recommend_retention_minutes(
            phase_mode, fluids.pressure_psia, fluids.temperature_f
        )

    retention = RetentionSettings(oil_minutes=oil_min, water_minutes=water_min, custom=use_custom_retention)

    default_k = 0.167 if separator_type == "vertical" else 0.45
    inputs = DesignInputs(
        separator_type=separator_type,
        phase_mode=phase_mode,
        fluids=fluids,
        flows=flows,
        retention=retention,
        k_factor=float(payload.get("k_factor", default_k)),
        shell_height_ft=float(payload.get("shell_height_ft", 10)),
        liquid_fraction=float(payload.get("liquid_fraction", 0.5)),
        ld_ratio_target=float(payload.get("ld_ratio_target", 4.0)),
    )

    result = size_vertical(inputs) if separator_type == "vertical" else size_horizontal(inputs)

    return {
        "result": {
            "separator_type": result.separator_type,
            "phase_mode": result.phase_mode,
            "diameter_ft": round(result.diameter_ft, 3),
            "diameter_in": result.diameter_in,
            "length_ft": round(result.length_ft, 2),
            "liquid_height_ft": round(result.liquid_height_ft, 2),
            "ld_ratio": result.ld_ratio,
            "governing_constraint": result.governing_constraint,
            "constraints": [
                {
                    "name": c.name,
                    "governing": c.governing,
                    "diameter_ft": round(c.diameter_ft, 3),
                    "length_or_height_ft": round(c.length_or_height_ft, 2),
                    "capacity_value": round(c.capacity_value, 2),
                    "capacity_unit": c.capacity_unit,
                    "formula": c.formula,
                }
                for c in result.constraints
            ],
            "fluid_summary": result.fluid_summary,
            "retention_summary": {**result.retention_summary, "note": ret_note},
            "curve_data": result.curve_data,
        }
    }
