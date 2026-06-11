"""Motor-CAD connection wrapper.

Provides a simplified interface to connect to Motor-CAD,
run simulations, and extract results. Uses pymotorcad under the hood.
Supports both installed pymotorcad and local source fallback.
"""

from dataclasses import dataclass
from typing import Optional
import os
import sys
import json


def _get_pymotorcad_path() -> str:
    """Find pymotorcad installation or local source."""
    # Check local source first
    local_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pymotorcad", "src"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pymotorcad", "src"),
    ]
    for p in local_paths:
        abs_p = os.path.abspath(p)
        if os.path.isdir(abs_p):
            if abs_p not in sys.path:
                sys.path.insert(0, abs_p)
            return abs_p
    return ""


PYMOTORCAD_PATH = _get_pymotorcad_path()
PYMOTORCAD_AVAILABLE = False

# Try importing
try:
    from ansys.motorcad.core import MotorCAD
    PYMOTORCAD_AVAILABLE = True
except ImportError:
    try:
        if PYMOTORCAD_PATH:
            from ansys.motorcad.core import MotorCAD
            PYMOTORCAD_AVAILABLE = True
    except ImportError:
        pass


class MotorCADConnector:
    """Wrapper around pymotorcad MotorCAD class.

    Handles connection lifecycle, provides convenience methods
    for common simulation workflows, and extracts structured results.
    Works in both connected mode (real Motor-CAD) and offline mode (simulated).
    """

    def __init__(self, offline_mode: bool = False):
        self._mc = None
        self._connected = False
        self._offline_mode = offline_mode or not PYMOTORCAD_AVAILABLE
        self._simulated_params: dict = {}
        self._simulated_results: dict = {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_offline(self) -> bool:
        return self._offline_mode

    # ---- Connection ----

    def connect(self, port: int = -1, open_new: bool = True) -> bool:
        """Connect to Motor-CAD instance."""
        if self._offline_mode:
            self._connected = True
            return True

        try:
            self._mc = MotorCAD(
                port=port,
                open_new_instance=open_new,
                enable_exceptions=True,
            )
            self._connected = True
            return True
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

    # ---- Project Operations ----

    def load_project(self, filepath: str):
        if self._offline_mode:
            return
        self._ensure_connected()
        self._mc.load_from_file(filepath)

    def save_project(self, filepath: str):
        if self._offline_mode:
            return
        self._ensure_connected()
        self._mc.save_to_file(filepath)

    # ---- Parameter Access ----

    def get_variable(self, name: str) -> float:
        if self._offline_mode:
            return self._simulated_params.get(name)
        self._ensure_connected()
        return self._mc.get_variable(name)

    def set_variable(self, name: str, value: float):
        if self._offline_mode:
            self._simulated_params[name] = value
            return
        self._ensure_connected()
        self._mc.set_variable(name, value)

    def set_batch_variables(self, changes: dict):
        """Apply multiple variable changes at once."""
        for name, value in changes.items():
            self.set_variable(name, value)

    def get_parameter(self, name: str):
        if self._offline_mode:
            return self._simulated_params.get(name)
        self._ensure_connected()
        return self._mc.get_parameter(name)

    # ---- Simulation ----

    def run_electromagnetic(self) -> dict:
        if self._offline_mode:
            return self._simulated_results.get("em", {})
        self._ensure_connected()
        self._mc.do_magnetic_calculation()
        return self._extract_em_results()

    def run_thermal(self) -> dict:
        if self._offline_mode:
            return self._simulated_results.get("thermal", {})
        self._ensure_connected()
        self._mc.do_thermal_calculation()
        return self._extract_thermal_results()

    def set_simulated_results(self, em: dict = None, thermal: dict = None):
        """Set simulated results for offline mode."""
        if em:
            self._simulated_results["em"] = em
        if thermal:
            self._simulated_results["thermal"] = thermal

    # ---- Geometry overview ----

    def get_geometry_overview(self) -> dict:
        if self._offline_mode:
            return {k: v for k, v in self._simulated_params.items()
                    if k in self._GEO_VARS}
        self._ensure_connected()
        params = {}
        for var in self._GEO_VARS:
            try:
                params[var] = self.get_variable(var)
            except Exception:
                params[var] = None
        return params

    _GEO_VARS = [
        "Stator_Lam_Dia", "Stator_Bore", "Airgap",
        "Stack_Length", "Slot_Number", "Pole_Number",
        "Tooth_Width", "Slot_Depth", "Stator_Yoke_Width",
        "Magnet_Thickness", "Magnet_Arc", "Pole_Embrace",
        "Slot_Opening", "Rotor_Outer_Dia",
    ]

    def get_material_overview(self) -> dict:
        materials = {}
        mat_vars = [
            "Stator_Lam_Material", "Rotor_Lam_Material",
            "Magnet_Material", "Shaft_Material",
            "Copper_Material", "Sleeve_Material",
        ]
        for var in mat_vars:
            try:
                materials[var] = self.get_variable(var)
            except Exception:
                materials[var] = None
        return materials

    # ---- Full state ----

    def get_full_state(self) -> dict:
        """Get comprehensive design state as a dict for AI analysis."""
        geometry = self.get_geometry_overview()
        em = self._extract_em_results() if not self._offline_mode else self._simulated_results.get("em", {})
        thermal = self._extract_thermal_results() if not self._offline_mode else self._simulated_results.get("thermal", {})

        return {
            "geometry": geometry,
            "materials": self.get_material_overview(),
            "em_results": em,
            "thermal_results": thermal,
        }

    # ---- Internal ----

    def _ensure_connected(self):
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

    def _safe_get(self, var_name: str, default=None):
        try:
            return self.get_variable(var_name)
        except Exception:
            return default

    def _extract_em_results(self) -> dict:
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
        return {
            "winding_temp_max": self._safe_get("Winding_Temp_Max"),
            "winding_temp_avg": self._safe_get("Winding_Temp_Avg"),
            "pm_temp_max": self._safe_get("PM_Temp_Max"),
            "stator_temp_max": self._safe_get("Stator_Temp_Max"),
            "housing_temp_avg": self._safe_get("Housing_Temp_Avg"),
            "coolant_temp_rise": self._safe_get("Coolant_Temp_Rise"),
        }