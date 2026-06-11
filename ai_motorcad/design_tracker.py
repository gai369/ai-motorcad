"""Design session tracker - records changes, compares against specs.

Tracks every parameter change and simulation snapshot.
Enables undo, session save/load, and spec-vs-actual comparison.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import json


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ChangeRecord:
    """A single parameter change."""
    timestamp: str = ""
    parameter: str = ""
    old_value: float = 0
    new_value: float = 0
    reason: str = ""

    def __str__(self):
        return (
            f"[{self.timestamp}] {self.parameter}: "
            f"{self.old_value:.3f} -> {self.new_value:.3f}"
            f"{' (' + self.reason + ')' if self.reason else ''}"
        )


@dataclass
class DesignSnapshot:
    """Complete design state at a simulation point."""
    timestamp: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)
    em_results: dict = field(default_factory=dict)
    thermal_results: dict = field(default_factory=dict)
    spec_comparison: dict = field(default_factory=dict)

    def has_results(self) -> bool:
        return bool(self.em_results) or bool(self.thermal_results)


@dataclass
class SessionLog:
    """Complete design session."""
    project_name: str = ""
    project_spec: dict = field(default_factory=dict)
    initial_design: dict = field(default_factory=dict)
    current_design: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    change_history: list = field(default_factory=list)
    snapshots: list = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_spec": self.project_spec,
            "initial_design": self.initial_design,
            "current_design": self.current_design,
            "parameters": self.parameters,
            "change_history": [asdict(c) if hasattr(c, '__dataclass_fields__') else c for c in self.change_history],
            "snapshots": [asdict(s) if hasattr(s, '__dataclass_fields__') else s for s in self.snapshots],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class SessionManager:
    """Manage design session lifecycle."""

    def __init__(self):
        self.session: Optional[SessionLog] = None
        self._undo_stack: list = []

    def new_session(self, project_name: str, project_spec: dict,
                    initial_design: dict) -> SessionLog:
        """Start a new design session."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params = initial_design.get("parameters", {}) if isinstance(initial_design, dict) else {}

        self.session = SessionLog(
            project_name=project_name,
            project_spec=project_spec,
            initial_design=initial_design if isinstance(initial_design, dict) else initial_design.to_dict(),
            current_design=initial_design if isinstance(initial_design, dict) else initial_design.to_dict(),
            parameters=dict(params),
            created_at=now,
            updated_at=now,
        )
        self._undo_stack = []
        return self.session

    def record_change(self, parameter: str, old_value: float,
                      new_value: float, reason: str = "") -> ChangeRecord:
        """Record a parameter change."""
        if not self.session:
            raise RuntimeError("No active session. Create one first.")

        now = datetime.now().strftime("%H:%M:%S")
        record = ChangeRecord(
            timestamp=now,
            parameter=parameter,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
        )

        # Save undo state
        self._undo_stack.append({
            "parameter": parameter,
            "value": old_value,
        })

        self.session.change_history.append(record)
        self.session.parameters[parameter] = new_value
        self.session.updated_at = now
        return record

    def record_simulation(self, description: str, parameters: dict,
                          em_results: dict, thermal_results: dict,
                          spec_comparison: dict) -> DesignSnapshot:
        """Record a simulation snapshot."""
        if not self.session:
            raise RuntimeError("No active session.")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot = DesignSnapshot(
            timestamp=now,
            description=description,
            parameters=dict(parameters),
            em_results=dict(em_results),
            thermal_results=dict(thermal_results),
            spec_comparison=dict(spec_comparison),
        )
        self.session.snapshots.append(snapshot)
        self.session.updated_at = now
        return snapshot

    def undo(self) -> Optional[ChangeRecord]:
        """Undo the last parameter change."""
        if not self._undo_stack:
            return None

        last = self._undo_stack.pop()
        param = last["parameter"]
        value = last["value"]
        old_value = self.session.parameters.get(param, value)

        now = datetime.now().strftime("%H:%M:%S")
        record = ChangeRecord(
            timestamp=now,
            parameter=param,
            old_value=old_value,
            new_value=value,
            reason="undo",
        )
        self.session.change_history.append(record)
        self.session.parameters[param] = value
        return record

    def get_last_snapshot(self) -> Optional[DesignSnapshot]:
        """Get the most recent simulation snapshot."""
        if self.session and self.session.snapshots:
            return self.session.snapshots[-1]
        return None

    def save_session(self, filepath: str):
        """Save session to JSON file."""
        if not self.session:
            raise RuntimeError("No active session.")
        data = self.session.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_session(self, filepath: str) -> SessionLog:
        """Load session from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.session = SessionLog(
            project_name=data.get("project_name", ""),
            project_spec=data.get("project_spec", {}),
            initial_design=data.get("initial_design", {}),
            current_design=data.get("current_design", {}),
            parameters=data.get("parameters", {}),
            change_history=data.get("change_history", []),
            snapshots=data.get("snapshots", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        return self.session


# ---------------------------------------------------------------------------
# Spec Comparator
# ---------------------------------------------------------------------------

class SpecComparator:
    """Compare current design results against project specifications."""

    def compare(self, em_results: dict, thermal_results: dict,
                spec: dict, geometry: dict = None) -> dict:
        """Compare simulation results against project specs.

        Returns a dict with comparisons: each key has target, actual, unit, status.
        """
        comparisons = {}

        # Torque comparison
        target_torque = spec.get("rated_torque_nm", 0)
        actual_torque = em_results.get("torque_avg", 0)
        if target_torque > 0 and actual_torque > 0:
            diff_pct = (actual_torque - target_torque) / target_torque * 100
            comparisons["Rated Torque"] = {
                "target": target_torque, "actual": actual_torque,
                "unit": "Nm", "diff_pct": round(diff_pct, 1),
                "status": self._status(diff_pct, -5, 5),
            }

        # Efficiency
        target_eff = spec.get("target_efficiency_pct", 0)
        actual_eff = em_results.get("efficiency", 0)
        if target_eff > 0 and actual_eff > 0:
            diff_pct = actual_eff - target_eff
            comparisons["Efficiency"] = {
                "target": target_eff, "actual": actual_eff,
                "unit": "%", "diff_pct": round(diff_pct, 1),
                "status": self._status(diff_pct, -1, 0),
            }

        # Temperature (winding)
        actual_temp = thermal_results.get("winding_temp_max", 0)
        if actual_temp > 0:
            target_temp = spec.get("max_winding_temp", 155)
            diff_pct = (actual_temp - target_temp) / target_temp * 100
            comparisons["Winding Temp"] = {
                "target": f"<{target_temp}", "actual": actual_temp,
                "unit": "degC", "diff_pct": round(diff_pct, 1),
                "status": self._status(-diff_pct, 0, 10),
            }

        # PM temperature
        actual_pm_temp = thermal_results.get("pm_temp_max", 0)
        if actual_pm_temp > 0:
            target_pm_temp = 150
            comparisons["PM Temp"] = {
                "target": f"<{target_pm_temp}", "actual": actual_pm_temp,
                "unit": "degC", "diff_pct": 0,
                "status": "ok" if actual_pm_temp < target_pm_temp else "warning",
            }

        # Dimensions
        if geometry:
            dia = geometry.get("Stator_Lam_Dia", 0)
            target_dia = spec.get("max_outer_diameter_mm", 0)
            if target_dia > 0 and dia > 0:
                comparisons["Outer Diameter"] = {
                    "target": f"<={target_dia}", "actual": dia,
                    "unit": "mm", "diff_pct": 0,
                    "status": "ok" if dia <= target_dia else "critical",
                }

            stack = geometry.get("Stack_Length", 0)
            target_stack = spec.get("max_stack_length_mm", 0)
            if target_stack > 0 and stack > 0:
                comparisons["Stack Length"] = {
                    "target": f"<={target_stack}", "actual": stack,
                    "unit": "mm", "diff_pct": 0,
                    "status": "ok" if stack <= target_stack else "critical",
                }

        return comparisons

    def format_comparison(self, comparisons: dict) -> str:
        """Format comparison as a readable table."""
        if not comparisons:
            return "No comparison data available."

        icons = {"ok": "[OK]", "warning": "[WARN]", "critical": "[CRIT]", "": "?"}
        lines = [
            "Spec Comparison:",
            f"  {'Metric':<20s} {'Target':<15s} {'Actual':<15s} {'Status':<8s}"
        ]
        lines.append(f"  {'-'*18} {'-'*13} {'-'*13} {'-'*6}")

        for name, data in comparisons.items():
            icon = icons.get(data.get("status", ""), "?")
            diff = data.get("diff_pct", 0)
            diff_str = f" ({diff:+.1f}%)" if diff != 0 else ""
            lines.append(
                f"  {name:<20s} {str(data['target']):<15s} "
                f"{str(data['actual']):<15s} {icon} {data.get('status', '')}{diff_str}"
            )
        return "\n".join(lines)

    def _status(self, diff_pct: float, warn_low: float, warn_high: float) -> str:
        if diff_pct < warn_low - 5:
            return "critical"
        elif diff_pct < warn_low:
            return "warning"
        elif diff_pct > warn_high:
            return "warning"
        return "ok"