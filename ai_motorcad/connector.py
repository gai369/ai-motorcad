"""Motor-CAD connection wrapper.

Provides a simplified interface to connect to Motor-CAD,
run simulations, and extract results. Uses pymotorcad under the hood.
"""

from dataclasses import dataclass
from typing import Optional
import json


class MotorCADConnector:
    """Wrapper around pymotorcad MotorCAD class.

    Handles connection lifecycle, provides convenience methods
    for common simulation workflows, and extracts structured results.
    """

    def __init__(self):
        self._mc = None
        self._connected = False

    def connect(self, port: int = -1, open_new: bool = True) -> bool:
        """Connect to Motor-CAD instance."""
        try:
            from ansys.motorcad.core import MotorCAD
            self._mc = MotorCAD(
                port=port,
                open_new_instance=open_new,
                enable_exceptions=True,
            )
            self._connected = True
            return True
        except ImportError:
            raise RuntimeError(
                "pymotorcad not installed. Run: pip install ansys-pymotorcad"
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Motor-CAD: {e}")

    def disconnect(self):
        """Close Motor-CAD connection."""
        if self._mc is not None:
            try:
                self._mc.quit()
            except Exception:
                pass
            self._mc = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def load_project(self, filepath: str):
        """Load a Motor-CAD project file."""
        self._ensure_connected()
        self._mc.load_from_file(filepath)

    def save_project(self, filepath: str):
        """Save current Motor-CAD project."""
        self._ensure_connected()
        self._mc.save_to_file(filepath)

    def run_electromagnetic(self) -> dict:
        """Run electromagnetic simulation and return key results."""
        self._ensure_connected()
        self._mc.do_magnetic_calculation()
        return self._extract_em_results()

    def run_thermal(self) -> dict:
        """Run thermal simulation and return key results."""
        self._ensure_connected()
        self._mc.do_thermal_calculation()
        return self._extract_thermal_results()

    def run_lab(self, speed_rpm: float, current_arms: float,
                gamma_deg: float = 0) -> dict:
        """Run efficiency map calculation at an operating point."""
        self._ensure_connected()
        self._mc.set_variable("Speed", speed_rpm)
        self._mc.set_variable("PhaseCurrent", current_arms)
        self._mc.set_variable("Gamma", gamma_deg)
        self._mc.do_lab_calculation()
        return self._extract_lab_point()

    def get_variable(self, name: str) -> float:
        """Get a Motor-CAD variable value."""
        self._ensure_connected()
        return self._mc.get_variable(name)

    def set_variable(self, name: str, value: float):
        """Set a Motor-CAD variable."""
        self._ensure_connected()
        self._mc.set_variable(name, value)

    def get_parameter(self, name: str):
        """Get a Motor-CAD parameter."""
        self._ensure_connected()
        return self._mc.get_parameter(name)

    def get_geometry_overview(self) -> dict:
        """Extract key geometry parameters in a structured dict."""
        self._ensure_connected()
        params = {}
        geo_vars = [
            "Stator_Lam_Dia", "Stator_Bore", "Airgap",
            "Stack_Length", "Slot_Number", "Pole_Number",
            "Tooth_Width", "Slot_Depth", "Stator_Yoke_Width",
            "Magnet_Thickness", "Magnet_Arc", "Pole_Embrace",
        ]
        for var in geo_vars:
            try:
                params[var] = self.get_variable(var)
            except Exception:
                params[var] = None
        return params

    def get_material_overview(self) -> dict:
        """Extract material assignments."""
        self._ensure_connected()
        materials = {}
        mat_vars = [
            "Stator_Lam_Material", "Rotor_Lam_Material",
            "Magnet_Material", "Shaft_Material",
            "Copper_Material", "Sleeve_Material",
        ]
        for var in mat_vars:
            try:
                materials[var] = self._mc.get_variable(var)
            except Exception:
                materials[var] = None
        return materials

    def _ensure_connected(self):
        if not self._connected or self._mc is None:
            raise RuntimeError("Not connected to Motor-CAD. Call connect() first.")

    def _safe_get(self, var_name: str, default=None):
        try:
            return self.get_variable(var_name)
        except Exception:
            return default

    def _extract_em_results(self) -> dict:
        """Extract electromagnetic simulation results."""
        return {
            "torque_avg": self._safe_get("Torque_Average"),
            "torque_ripple_pct": self._safe_get("Torque_Ripple_Pct"),
            "cogging_torque": self._safe_get("Cogging_Torque"),
            "line_voltage_rms": self._safe_get("Line_Voltage_RMS"),
            "phase_current_rms": self._safe_get("PhaseCurrent_RMS"),
            "power_factor": self._safe_get("Power_Factor"),
            "total_loss": self._safe_get("Total_Loss"),
            "copper_loss": self._safe_get("Copper_Loss"),
            "iron_loss": self._safe_get("Iron_Loss"),
            "pm_loss": self._safe_get("PM_Loss"),
            "efficiency": self._safe_get("Efficiency"),
            "airgap_flux_density": self._safe_get("Airgap_Flux_Density_Peak"),
            "tooth_flux_density": self._safe_get("Tooth_Flux_Density_Max"),
            "yoke_flux_density": self._safe_get("Stator_Yoke_Flux_Density_Max"),
        }

    def _extract_thermal_results(self) -> dict:
        """Extract thermal simulation results."""
        return {
            "winding_temp_max": self._safe_get("Winding_Temp_Max"),
            "winding_temp_avg": self._safe_get("Winding_Temp_Avg"),
            "pm_temp_max": self._safe_get("PM_Temp_Max"),
            "stator_temp_max": self._safe_get("Stator_Temp_Max"),
            "housing_temp_avg": self._safe_get("Housing_Temp_Avg"),
            "coolant_temp_rise": self._safe_get("Coolant_Temp_Rise"),
        }

    def _extract_lab_point(self) -> dict:
        """Extract lab calculation results at one point."""
        return {
            "torque": self._safe_get("Torque_Out"),
            "speed": self._safe_get("Speed"),
            "power_out": self._safe_get("Power_Out"),
            "efficiency": self._safe_get("Efficiency"),
            "total_loss": self._safe_get("Total_Loss"),
            "phase_voltage": self._safe_get("PhaseVoltage"),
            "phase_current": self._safe_get("PhaseCurrent"),
            "power_factor": self._safe_get("Power_Factor"),
        }

    def get_full_state(self) -> dict:
        """Get comprehensive design state as a dict for AI analysis."""
        return {
            "geometry": self.get_geometry_overview(),
            "materials": self.get_material_overview(),
            "em_results": self._extract_em_results(),
            "thermal_results": self._extract_thermal_results(),
        }