"""Electromagnetic design knowledge base - rules, heuristics and domain expertise.

This module encodes motor design principles that the AI assistant uses
to analyze designs and suggest improvements. No ML training required -
this is pure domain knowledge.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MotorType(Enum):
    """Supported motor topologies."""
    BPM = "BPM"
    SPM = "SPM"
    IPM = "IPM"
    INDUCTION = "IM"
    SYNRM = "SynRM"
    PM_ASSISTED_SYNRM = "PMASynRM"
    WOUND_FIELD = "WFSM"
    SWITCHED_RELUCTANCE = "SRM"


class CoolingType(Enum):
    """Cooling methods."""
    NATURAL = "natural_convection"
    FORCED_AIR = "forced_air"
    WATER_JACKET = "water_jacket"
    OIL_SPRAY = "oil_spray"
    OIL_IMMERSION = "oil_immersion"


@dataclass
class DesignTarget:
    """Design targets and constraints."""
    power_kw: float = 0.0
    speed_rpm: float = 0.0
    torque_nm: float = 0.0
    dc_voltage: float = 0.0
    max_current_arms: float = 0.0
    target_efficiency: float = 95.0
    max_outer_diameter_mm: float = 300.0
    max_stack_length_mm: float = 200.0
    max_current_density: float = 15.0
    cooling: CoolingType = CoolingType.WATER_JACKET


@dataclass
class AnalysisResult:
    """Structured analysis of a motor design."""
    parameter: str
    current_value: float
    unit: str
    expected_range: tuple
    status: str
    suggestion: str


DESIGN_RULES = {
    "electromagnetic": {
        "airgap_flux_density": {
            "range": (0.7, 1.05),
            "unit": "T",
            "description": "Peak airgap flux density (fundamental)",
            "rule_of_thumb": (
                "0.7-0.85 T for low-cost ferrite PMs; "
                "0.85-1.05 T for NdFeB PMs. "
                "Higher values increase torque density but risk saturation."
            ),
        },
        "stator_tooth_flux_density": {
            "range": (1.4, 1.8),
            "unit": "T",
            "description": "Peak stator tooth flux density",
            "rule_of_thumb": (
                "1.4-1.6 T for low iron loss designs; "
                "1.6-1.8 T for compact designs. "
                ">1.8 T causes significant iron loss increase."
            ),
        },
        "stator_yoke_flux_density": {
            "range": (1.2, 1.6),
            "unit": "T",
            "description": "Peak stator yoke flux density",
            "rule_of_thumb": (
                "1.2-1.5 T typical. Lower than tooth to reduce yoke iron loss. "
                ">1.6 T may cause vibration and noise issues."
            ),
        },
        "current_density_rms": {
            "range": (3, 20),
            "unit": "A/mm^2",
            "description": "RMS current density in winding",
            "rule_of_thumb": (
                "3-8 A/mm^2: natural convection (small machines); "
                "8-15 A/mm^2: forced air / water jacket; "
                "15-20 A/mm^2: oil spray / immersion cooling. "
                "Higher density = smaller machine but more cooling needed."
            ),
        },
        "torque_ripple_pct": {
            "range": (0, 25),
            "unit": "%",
            "description": "Torque ripple (peak-to-peak / average)",
            "rule_of_thumb": (
                "<5%: excellent (EV traction grade); "
                "5-10%: good (industrial servo); "
                "10-20%: acceptable (fan/pump); "
                ">20%: needs improvement. "
                "Consider: skewing, slot/pole combination, PM shaping, or current harmonics."
            ),
        },
        "cogging_torque_ratio": {
            "range": (0, 10),
            "unit": "%",
            "description": "Cogging torque / rated torque",
            "rule_of_thumb": (
                "<1%: excellent; <3%: good; >5%: needs improvement. "
                "Reduce by: stator slot skew, PM pole arc optimization, "
                "slot opening reduction, dummy slots, or fractional slot winding."
            ),
        },
    },
    "thermal": {
        "winding_temperature_max": {
            "range": (80, 180),
            "unit": "degC",
            "description": "Maximum winding hot-spot temperature",
            "rule_of_thumb": (
                "Class F (155 degC): keep below 145 degC for margin. "
                "Class H (180 degC): keep below 165 degC. "
                "Every 10 degC rise halves insulation life (Arrhenius)."
            ),
        },
        "pm_temperature_max": {
            "range": (80, 180),
            "unit": "degC",
            "description": "Maximum PM temperature",
            "rule_of_thumb": (
                "NdFeB: keep below 120 degC (SH grade) or 150 degC (UH/EH grade). "
                "Ferrite: watch for demagnetization at low temp (< -20 degC). "
                "SmCo: good up to 250+ degC."
            ),
        },
    },
    "mechanical": {
        "rotor_tip_speed": {
            "range": (30, 200),
            "unit": "m/s",
            "description": "Rotor outer surface linear speed",
            "rule_of_thumb": (
                "<80 m/s: standard IPM with simple sleeve; "
                "80-150 m/s: carbon fiber sleeve recommended; "
                ">150 m/s: high-speed design, special rotor retention needed."
            ),
        },
        "slot_fill_factor": {
            "range": (0.35, 0.70),
            "unit": "ratio",
            "description": "Copper area / slot area",
            "rule_of_thumb": (
                "0.35-0.45: round wire, random wound; "
                "0.45-0.55: round wire, precision wound; "
                "0.55-0.70: hairpin / rectangular wire. "
                "Higher fill factor = lower DC resistance = higher efficiency."
            ),
        },
    },
}

SLOT_POLE_RECOMMENDATIONS = {
    (12, 8): {"kw": 0.866, "comment": "Popular for small PM motors, concentrated winding"},
    (12, 10): {"kw": 0.933, "comment": "Good winding factor, moderate cogging"},
    (12, 14): {"kw": 0.933, "comment": "High pole count, good for direct drive"},
    (18, 12): {"kw": 0.866, "comment": "Low cogging, smooth torque"},
    (18, 16): {"kw": 0.945, "comment": "High winding factor, low torque ripple"},
    (24, 16): {"kw": 0.866, "comment": "Popular for EV traction motors"},
    (27, 6): {"kw": 0.866, "comment": "Lowest cogging, good for servo"},
    (36, 6): {"kw": 0.866, "comment": "Classic IM stator, can be used for PM"},
    (36, 8): {"kw": 0.945, "comment": "High winding factor, low cogging"},
    (48, 8): {"kw": 0.945, "comment": "Premium performance, EV traction grade"},
    (72, 12): {"kw": 0.945, "comment": "Large machines, very smooth torque"},
}

PM_MATERIALS = {
    "NdFeB_N35": {"Br": 1.17, "Hc": 890, "max_temp": 80, "cost": "medium"},
    "NdFeB_N42": {"Br": 1.30, "Hc": 955, "max_temp": 80, "cost": "medium"},
    "NdFeB_N48": {"Br": 1.38, "Hc": 995, "max_temp": 80, "cost": "high"},
    "NdFeB_35SH": {"Br": 1.17, "Hc": 890, "max_temp": 150, "cost": "high"},
    "NdFeB_42UH": {"Br": 1.28, "Hc": 955, "max_temp": 180, "cost": "very_high"},
    "SmCo_26": {"Br": 1.05, "Hc": 756, "max_temp": 250, "cost": "very_high"},
    "Ferrite_Y30": {"Br": 0.38, "Hc": 240, "max_temp": 250, "cost": "low"},
    "Ferrite_Y35": {"Br": 0.40, "Hc": 260, "max_temp": 250, "cost": "low"},
}

SUGGESTION_TEMPLATES = {
    "high_torque_ripple": [
        "Try rotor skew (typically 0.5-1.0 slot pitch)",
        "Optimize PM pole arc (typically 0.7-0.85 of pole pitch)",
        "Consider different slot/pole combination",
        "Add stator slot notches (dummy slots) to reduce cogging harmonics",
        "Check if current harmonics from drive are contributing",
    ],
    "low_efficiency": [
        "Check current density - if >15 A/mm^2, consider improving cooling or increasing slot area",
        "Review iron loss - high flux density in teeth (>1.8T) dramatically increases iron loss",
        "Check PM eddy current loss - consider PM segmentation (axial and/or circumferential)",
        "Verify winding configuration - distributed winding typically more efficient than concentrated",
        "Lower switching frequency may increase AC copper loss",
    ],
    "high_temperature": [
        "Reduce current density or improve cooling method",
        "Check if PM temperature is approaching grade limit",
        "Increase housing fin area or consider water jacket",
        "Review iron loss - it may be the dominant heat source at high speed",
        "Consider axial ventilation ducts for larger machines",
    ],
    "magnet_demag_risk": [
        "Check PM grade temperature rating vs. actual hot-spot",
        "Increase magnet thickness to reduce operating point",
        "Verify short-circuit current vs. PM knee point",
        "Consider SmCo for high-temperature applications",
        "Add flux barriers to limit demagnetizing field",
    ],
    "high_cogging": [
        "Use fractional slot winding to increase cogging frequency and reduce amplitude",
        "Optimize slot opening width (narrower = lower cogging, but harder to wind)",
        "Add stator tooth shoe shaping (notches or asymmetry)",
        "Skew stator or rotor by one slot pitch",
        "Adjust PM pole arc to minimize cogging harmonics",
    ],
    "saturation_risk": [
        "Widen stator teeth (reduce slot area, check fill factor)",
        "Increase stator yoke thickness",
        "Reduce airgap flux density (thicker magnet or lower Br grade)",
        "Check if rotor iron is also saturating",
        "Consider higher-grade lamination steel (M250 vs M400)",
    ],
}