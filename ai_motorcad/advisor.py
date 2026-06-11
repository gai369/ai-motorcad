"""Design advisor - generates actionable suggestions from analysis results.

The advisor maps analysis issues to concrete, actionable suggestions
based on electromagnetic design principles.
"""

from dataclasses import dataclass, field
from typing import Optional

from .knowledge import SUGGESTION_TEMPLATES, SLOT_POLE_RECOMMENDATIONS, PM_MATERIALS
from .analyzer import DesignCheck, DesignReport, Severity


@dataclass
class Suggestion:
    """A single design improvement suggestion."""
    priority: int
    category: str
    title: str
    detail: str
    expected_impact: str
    effort: str
    relates_to: str


class MotorAdvisor:
    """Generate prioritized design improvement suggestions."""

    def suggest(self, report: DesignReport,
                design_state: Optional[dict] = None) -> list:
        """Generate prioritized suggestions based on analysis report."""
        suggestions = []

        for check in report.checks:
            if check.severity == Severity.OK:
                continue
            suggestions.extend(
                self._suggest_for_check(check, design_state)
            )

        seen = set()
        unique = []
        for s in sorted(suggestions, key=lambda x: x.priority):
            if s.title not in seen:
                seen.add(s.title)
                unique.append(s)
        return unique

    def _suggest_for_check(self, check: DesignCheck,
                           design_state: Optional[dict]) -> list:
        results = []
        priority = 1 if check.severity == Severity.CRITICAL else 3

        mapping = {
            "torque_ripple_pct": self._suggest_torque_ripple,
            "cogging_torque_ratio": self._suggest_cogging,
            "airgap_flux_density": self._suggest_flux_density,
            "stator_tooth_flux_density": self._suggest_saturation,
            "stator_yoke_flux_density": self._suggest_saturation,
            "current_density_rms": self._suggest_current_density,
            "winding_temp_max": self._suggest_temperature,
            "pm_temp_max": self._suggest_pm_temp,
            "rotor_tip_speed": self._suggest_tip_speed,
            "efficiency": self._suggest_efficiency,
        }

        handler = mapping.get(check.name)
        if handler:
            results.extend(handler(check, design_state, priority))
        else:
            results.append(Suggestion(
                priority=priority, category="general",
                title=f"Review {check.name}",
                detail=check.suggestion or check.message,
                expected_impact="Depends on severity",
                effort="medium", relates_to=check.name,
            ))
        return results

    def _suggest_torque_ripple(self, check, state, pri):
        suggestions = []
        templates = SUGGESTION_TEMPLATES["high_torque_ripple"]
        for i, tmpl in enumerate(templates):
            suggestions.append(Suggestion(
                priority=pri + i, category="geometry",
                title=f"Reduce torque ripple: method {i+1}",
                detail=tmpl,
                expected_impact="Reduced torque ripple and vibration",
                effort="medium" if "skew" in tmpl.lower() or "optimize" in tmpl.lower() else "low",
                relates_to=check.name,
            ))
        return suggestions

    def _suggest_cogging(self, check, state, pri):
        suggestions = []
        for i, tmpl in enumerate(SUGGESTION_TEMPLATES["high_cogging"]):
            suggestions.append(Suggestion(
                priority=pri + i, category="geometry",
                title=f"Reduce cogging torque: method {i+1}",
                detail=tmpl,
                expected_impact="Reduced cogging torque and acoustic noise",
                effort="medium", relates_to=check.name,
            ))
        return suggestions

    def _suggest_flux_density(self, check, state, pri):
        if check.value < check.range_min:
            detail = (
                f"Airgap flux density is {check.value:.2f} T, below target. "
                "Consider: (1) Increase magnet thickness or use higher Br grade, "
                "(2) Reduce airgap length, (3) Check if demagnetization is occurring."
            )
        else:
            detail = (
                f"Airgap flux density is {check.value:.2f} T, above typical range. "
                "Stator teeth likely saturating. Consider increasing tooth width "
                "or reducing magnet strength."
            )
        return [Suggestion(
            priority=pri, category="magnetic",
            title="Adjust airgap flux density", detail=detail,
            expected_impact="Better flux utilization and reduced saturation",
            effort="low", relates_to=check.name,
        )]

    def _suggest_saturation(self, check, state, pri):
        location = "tooth" if "tooth" in check.name else "yoke"
        detail = (
            f"{location.title()} flux density at {check.value:.2f} T exceeds target. "
            f"Options: (1) Widen {location} (may reduce slot area), "
            "(2) Use higher-grade lamination steel (e.g., M250->M190), "
            "(3) Reduce airgap flux density."
        )
        return [Suggestion(
            priority=pri, category="magnetic",
            title=f"Reduce {location} saturation", detail=detail,
            expected_impact="Lower iron loss and better overload capability",
            effort="low", relates_to=check.name,
        )]

    def _suggest_current_density(self, check, state, pri):
        if check.value > check.range_max:
            detail = (
                f"Current density is {check.value:.2f} A/mm^2, which is high. "
                "Options: (1) Increase slot area (wider slot or deeper), "
                "(2) Improve cooling method, (3) Reduce rated current, "
                "(4) Use hairpin winding for better fill factor."
            )
        else:
            detail = f"Current density is low at {check.value:.2f} A/mm^2. Room to increase for more compact design."
        return [Suggestion(
            priority=pri, category="winding",
            title="Optimize current density", detail=detail,
            expected_impact="Better thermal management or more compact design",
            effort="medium", relates_to=check.name,
        )]

    def _suggest_temperature(self, check, state, pri):
        location = "winding" if "winding" in check.name else "stator"
        detail = (
            f"{location.title()} temperature at {check.value:.0f} degC exceeds target. "
            "(1) Improve cooling: increase flow rate, reduce inlet temp, "
            "(2) Reduce loss: lower current density or use lower-loss lamination, "
            "(3) Enhance heat transfer: add potting, improve housing fins."
        )
        return [Suggestion(
            priority=pri, category="thermal",
            title=f"Reduce {location} temperature", detail=detail,
            expected_impact="Improved reliability and longer insulation life",
            effort="medium", relates_to=check.name,
        )]

    def _suggest_pm_temp(self, check, state, pri):
        detail = (
            f"PM temperature at {check.value:.0f} degC is high. "
            "(1) Verify PM grade can handle this temperature, "
            "(2) Consider PM segmentation to reduce eddy current heating, "
            "(3) Improve rotor cooling, (4) Switch to higher-grade PM (e.g., SH->UH)."
        )
        return [Suggestion(
            priority=pri, category="thermal",
            title="Reduce PM temperature or upgrade PM grade", detail=detail,
            expected_impact="Prevent PM demagnetization, ensure reliable operation",
            effort="medium", relates_to=check.name,
        )]

    def _suggest_tip_speed(self, check, state, pri):
        detail = (
            f"Rotor tip speed is {check.value:.0f} m/s. "
            "(1) If >150 m/s: carbon fiber sleeve required for PM retention, "
            "(2) If >200 m/s: review rotor mechanical stress and bearing selection, "
            "(3) Consider reducing rotor diameter or operating speed."
        )
        return [Suggestion(
            priority=pri, category="mechanical",
            title="Review rotor mechanical design", detail=detail,
            expected_impact="Mechanical integrity at high speed",
            effort="high", relates_to=check.name,
        )]

    def _suggest_efficiency(self, check, state, pri):
        loss_analysis = (
            "To improve efficiency: (1) Identify dominant loss: copper, iron, or PM eddy. "
            "(2) Copper loss dominant: reduce current density or improve fill factor. "
            "(3) Iron loss dominant: use thinner laminations (0.35mm->0.20mm) or lower flux density. "
            "(4) PM loss dominant: segment magnets axially and circumferentially. "
            "(5) Mechanical loss: improve bearing selection, reduce windage."
        )
        return [Suggestion(
            priority=pri, category="efficiency",
            title="Improve motor efficiency", detail=loss_analysis,
            expected_impact="Each 1% efficiency gain saves significant energy over lifetime",
            effort="varies", relates_to=check.name,
        )]