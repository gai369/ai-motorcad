"""Design analyzer - compares simulation results against design rules.

The analyzer is the brain of the AI assistant. It takes Motor-CAD simulation
results, checks them against electromagnetic design rules, and produces
structured analysis that the advisor uses to generate suggestions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import math

from .knowledge import DESIGN_RULES, SLOT_POLE_RECOMMENDATIONS


class Severity(Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DesignCheck:
    """A single design check result."""
    name: str
    category: str
    value: Optional[float]
    unit: str
    range_min: float
    range_max: float
    severity: Severity
    message: str
    suggestion: str = ""


@dataclass
class DesignReport:
    """Complete design analysis report."""
    checks: list = field(default_factory=list)
    overall_score: float = 100.0
    critical_count: int = 0
    warning_count: int = 0
    summary: str = ""


class MotorAnalyzer:
    """Analyze motor design against electromagnetic design rules."""

    def __init__(self):
        self._rules = DESIGN_RULES
        self._checks: list = []

    def analyze(self, design_state: dict) -> DesignReport:
        """Run full design analysis."""
        self._checks = []

        em = design_state.get("em_results", {})
        thermal = design_state.get("thermal_results", {})
        geometry = design_state.get("geometry", {})

        self._check_flux_density(em)
        self._check_torque_quality(em)
        self._check_efficiency(em)
        self._check_current_density(em)
        self._check_temperatures(thermal)
        self._check_rotor_speed(geometry, em)

        return self._build_report()

    def _check_flux_density(self, em: dict):
        checks = [
            ("airgap_flux_density", em.get("airgap_flux_density")),
            ("stator_tooth_flux_density", em.get("tooth_flux_density")),
            ("stator_yoke_flux_density", em.get("yoke_flux_density")),
        ]
        for name, value in checks:
            rule = self._rules["electromagnetic"].get(name)
            if rule and value is not None:
                self._checks.append(self._evaluate(
                    name=name, category="electromagnetic", value=value,
                    unit=rule["unit"], rule_range=rule["range"],
                    rule_text=rule.get("rule_of_thumb", ""),
                ))

    def _check_torque_quality(self, em: dict):
        for key, name in [
            ("torque_ripple_pct", "torque_ripple_pct"),
            ("cogging_torque", "cogging_torque_ratio"),
        ]:
            value = em.get(key)
            rule = self._rules["electromagnetic"].get(name)
            if rule and value is not None:
                self._checks.append(self._evaluate(
                    name=name, category="electromagnetic", value=value,
                    unit=rule["unit"], rule_range=rule["range"],
                    rule_text=rule.get("rule_of_thumb", ""),
                ))

    def _check_efficiency(self, em: dict):
        eff = em.get("efficiency")
        if eff is not None:
            if eff < 80:
                sev = Severity.CRITICAL
                msg = f"Efficiency is critically low at {eff:.1f}%"
            elif eff < 90:
                sev = Severity.WARNING
                msg = f"Efficiency below typical target at {eff:.1f}%"
            elif eff < 94:
                sev = Severity.INFO
                msg = f"Efficiency is moderate at {eff:.1f}%"
            else:
                sev = Severity.OK
                msg = f"Efficiency is good at {eff:.1f}%"

            self._checks.append(DesignCheck(
                name="efficiency", category="electromagnetic",
                value=eff, unit="%", range_min=0, range_max=100,
                severity=sev, message=msg,
                suggestion="" if sev == Severity.OK else (
                    "Check loss breakdown: identify dominant loss component "
                    "(copper, iron, or PM eddy current) and optimize accordingly."
                ),
            ))

    def _check_current_density(self, em: dict):
        value = em.get("current_density_rms")
        if value is not None:
            rule = self._rules["electromagnetic"]["current_density_rms"]
            self._checks.append(self._evaluate(
                name="current_density_rms", category="electromagnetic",
                value=value, unit=rule["unit"],
                rule_range=rule["range"],
                rule_text=rule["rule_of_thumb"],
            ))

    def _check_temperatures(self, thermal: dict):
        checks = [
            ("winding_temp_max", thermal.get("winding_temp_max"),
             self._rules["thermal"]["winding_temperature_max"]),
            ("pm_temp_max", thermal.get("pm_temp_max"),
             self._rules["thermal"]["pm_temperature_max"]),
        ]
        for name, value, rule in checks:
            if value is not None:
                self._checks.append(self._evaluate(
                    name=name, category="thermal", value=value,
                    unit=rule["unit"], rule_range=rule["range"],
                    rule_text=rule.get("rule_of_thumb", ""),
                ))

    def _check_rotor_speed(self, geometry: dict, em: dict):
        rotor_dia = geometry.get("Stator_Bore")
        speed = em.get("speed_rpm") or geometry.get("Speed")
        if rotor_dia and speed:
            tip_speed = math.pi * (rotor_dia / 1000) * speed / 60
            rule = self._rules["mechanical"]["rotor_tip_speed"]
            self._checks.append(self._evaluate(
                name="rotor_tip_speed", category="mechanical",
                value=tip_speed, unit=rule["unit"],
                rule_range=rule["range"],
                rule_text=rule["rule_of_thumb"],
            ))

    def _evaluate(self, name: str, category: str, value: float,
                  unit: str, rule_range: tuple, rule_text: str) -> DesignCheck:
        low, high = rule_range

        if low <= value <= high:
            return DesignCheck(
                name=name, category=category,
                value=value, unit=unit,
                range_min=low, range_max=high,
                severity=Severity.OK,
                message=f"{name}: {value:.2f} {unit} - within expected range [{low}-{high}]",
            )

        margin = 0.15
        if value < low:
            deviation = (low - value) / low
            direction = "below"
        else:
            deviation = (value - high) / high
            direction = "above"

        sev = Severity.CRITICAL if deviation > margin else Severity.WARNING

        return DesignCheck(
            name=name, category=category,
            value=value, unit=unit,
            range_min=low, range_max=high,
            severity=sev,
            message=(
                f"{name}: {value:.2f} {unit} - {direction} expected range "
                f"[{low}-{high}], deviation: {deviation:.0%}"
            ),
            suggestion=rule_text,
        )

    def _build_report(self) -> DesignReport:
        criticals = [c for c in self._checks if c.severity == Severity.CRITICAL]
        warnings = [c for c in self._checks if c.severity == Severity.WARNING]
        oks = [c for c in self._checks if c.severity == Severity.OK]

        score = 100.0
        score -= len(criticals) * 15
        score -= len(warnings) * 5
        score = max(0, min(100, score))

        lines = [f"Design Analysis Report - Score: {score:.0f}/100", "=" * 50]
        if criticals:
            lines.append(f"\n** CRITICAL Issues ({len(criticals)}):")
            for c in criticals:
                lines.append(f"  - {c.message}")
        if warnings:
            lines.append(f"\nWarnings ({len(warnings)}):")
            for w in warnings:
                lines.append(f"  - {w.message}")
        if not criticals and not warnings:
            lines.append("\nAll checks passed. No issues found.")
        lines.append(f"\nOK: {len(oks)} checks within expected range.")

        return DesignReport(
            checks=self._checks,
            overall_score=score,
            critical_count=len(criticals),
            warning_count=len(warnings),
            summary="\n".join(lines),
        )