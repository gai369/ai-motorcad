
"""Interactive chat-based motor design assistant.

Natural language conversation loop for motor electromagnetic design.
Supports file-based spec loading, parameter modification in Chinese/English,
simulation result tracking, and proactive improvement suggestions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable
import os, re, sys, json

from .connector import MotorCADConnector, PYMOTORCAD_AVAILABLE
from .analyzer import MotorAnalyzer, DesignReport, Severity
from .advisor import MotorAdvisor, Suggestion
from .reporter import DesignReporter
from .design_spec import (
    ProjectSpec, InitialDesign, InitialDesignGenerator,
    load_spec_from_file, parse_spec_from_text,
)
from .llm_advisor import LLMAdvisor, get_llm_advisor, has_llm
from .design_tracker import (
    SessionManager, SpecComparator, DesignSnapshot, ChangeRecord,
)
from .knowledge import (
    SLOT_POLE_RECOMMENDATIONS, PM_MATERIALS,
    SUGGESTION_TEMPLATES, DESIGN_RULES,
)

# ---- Parameter aliases ----
PARAM_ALIASES = {
    "stator_lam_dia": "Stator_Lam_Dia", "stator_bore": "Stator_Bore",
    "airgap": "Airgap", "stack_length": "Stack_Length",
    "slot_number": "Slot_Number", "pole_number": "Pole_Number",
    "tooth_width": "Tooth_Width", "slot_depth": "Slot_Depth",
    "stator_yoke_width": "Stator_Yoke_Width", "slot_opening": "Slot_Opening",
    "magnet_thickness": "Magnet_Thickness", "magnet_arc": "Magnet_Arc",
    "pole_embrace": "Pole_Embrace", "rotor_outer_dia": "Rotor_Outer_Dia",
}

PARAM_ALIASES.update({
    "\u5b9a\u5b50\u5916\u5f84": "Stator_Lam_Dia",
    "\u5b9a\u5b50\u5185\u5f84": "Stator_Bore",
    "\u6c14\u9699": "Airgap",
    "\u53e0\u957f": "Stack_Length",
    "\u94c1\u5fc3\u957f": "Stack_Length",
    "\u69fd\u6570": "Slot_Number",
    "\u6781\u6570": "Pole_Number",
    "\u9f7f\u5bbd": "Tooth_Width",
    "\u9f7f\u90e8\u5bbd\u5ea6": "Tooth_Width",
    "\u69fd\u6df1": "Slot_Depth",
    "\u8f6d\u5bbd": "Stator_Yoke_Width",
    "\u8f6d\u539a": "Stator_Yoke_Width",
    "\u8f6d\u90e8\u5bbd\u5ea6": "Stator_Yoke_Width",
    "\u69fd\u53e3\u5bbd": "Slot_Opening",
    "\u78c1\u94a2\u539a\u5ea6": "Magnet_Thickness",
    "\u78c1\u94a2": "Magnet_Thickness",
    "\u78c1\u94a2\u6781\u5f27": "Magnet_Arc",
    "\u6781\u5f27\u7cfb\u6570": "Pole_Embrace",
    "\u8f6c\u5b50\u5916\u5f84": "Rotor_Outer_Dia",
    "\u7ed5\u7ec4\u5302\u6570": "Turns_Per_Coil",
    "\u7ebf\u5f84": "Wire_Diameter",
})

PARAM_COUPLING = {
    "Slot_Number": [("Tooth_Width", "\u9f7f\u5bbd\u9700\u91cd\u65b0\u8ba1\u7b97"), ("Slot_Depth", "\u69fd\u6df1\u53ef\u80fd\u9700\u8c03\u6574")],
    "Pole_Number": [("Magnet_Arc", "\u78c1\u94a2\u6781\u5f27\u9700\u5339\u914d\u65b0\u6781\u6570"), ("Magnet_Thickness", "\u6781\u6570\u53d8\u5316\u5f71\u54cd\u78c1\u8def")],
    "Stator_Bore": [("Tooth_Width", "\u5b54\u5f84\u53d8\u5316\u5f71\u54cd\u9f7f\u5bbd"), ("Stator_Yoke_Width", "\u8f6d\u5bbd\u9700\u91cd\u65b0\u6821\u6838")],
    "Magnet_Thickness": [("Stator_Yoke_Width", "\u6c14\u9699\u78c1\u5bc6\u53d8\u5316\u5f71\u54cd\u8f6d\u90e8")],
}


# ---- Proactive Suggestion Engine ----
class ProactiveAdvisor:
    """Generates concrete, quantified improvement suggestions."""

    def analyze_and_suggest(self, em_results, thermal_results, spec, params, comparisons):
        suggestions = []

        # Torque gap
        torque_target = spec.get("rated_torque_nm", 0)
        torque_actual = em_results.get("torque_avg", 0)
        if torque_target > 0 and torque_actual > 0:
            gap = (torque_target - torque_actual) / torque_target
            if gap > 0.02:
                mt = params.get("Magnet_Thickness", 5)
                nt = round(mt * (1 + gap * 2.5), 1)
                nt = max(3, min(12, nt))
                suggestions.append({
                    "priority": 2,
                    "issue": f"Torque gap {gap*100:.1f}%",
                    "action": f"Magnet_Thickness {mt} -> {nt} mm",
                    "expected_impact": f"Estimated torque +{gap*200:.0f}%",
                    "side_effects": [f"Iron loss may +{gap*150:.0f}%", f"PM cost +{((nt/mt)-1)*100:.0f}%"],
                    "effort": "low",
                })

        # Efficiency gap
        eff_target = spec.get("target_efficiency_pct", 95)
        eff_actual = em_results.get("efficiency", 0)
        if eff_target > 0 and eff_actual > 0 and eff_actual < eff_target - 0.5:
            copper = em_results.get("copper_loss", 0)
            iron = em_results.get("iron_loss", 0)
            pm_loss = em_results.get("pm_loss", 0)
            total = em_results.get("total_loss", copper + iron + pm_loss)
            if total > 0:
                copper_pct = copper / total * 100
                iron_pct = iron / total * 100
                if copper_pct > iron_pct:
                    suggestions.append({
                        "priority": 1,
                        "issue": f"Efficiency gap {(eff_target-eff_actual):.1f}% (copper loss {copper_pct:.0f}%)",
                        "action": "Reduce current density or increase slot area",
                        "expected_impact": f"Per 10% copper loss reduction: efficiency +{copper/total*10:.1f}%",
                        "side_effects": ["Slot area increase may reduce tooth width"],
                        "effort": "medium",
                    })
                elif iron_pct > copper_pct:
                    tooth_fd = em_results.get("tooth_flux_density", 1.6)
                    if tooth_fd and tooth_fd > 1.7:
                        tw = params.get("Tooth_Width", 6)
                        nw = round(tw * (tooth_fd / 1.6), 1)
                        suggestions.append({
                            "priority": 1,
                            "issue": f"Efficiency gap {(eff_target-eff_actual):.1f}% (iron loss {iron_pct:.0f}%, tooth B={tooth_fd}T)",
                            "action": f"Tooth_Width {tw} -> {nw} mm (target 1.6T)",
                            "expected_impact": f"Estimated iron loss -{(tooth_fd-1.6)/1.6*100:.0f}%",
                            "side_effects": ["Slot area decreases -> copper loss may rise"],
                            "effort": "low",
                        })
                if pm_loss / total > 0.15:
                    suggestions.append({
                        "priority": 3,
                        "issue": f"PM eddy loss {pm_loss/total*100:.0f}% of total",
                        "action": "Segment PMs circumferentially (3-5 segments) + axially",
                        "expected_impact": "PM loss -40~60%",
                        "side_effects": ["Manufacturing cost increase"],
                        "effort": "medium",
                    })

        # Temperature
        winding_temp = thermal_results.get("winding_temp_max", 0)
        if winding_temp > 155:
            suggestions.append({
                "priority": 1,
                "issue": f"Winding temp {winding_temp:.0f}C over limit",
                "action": "Reduce current density or improve cooling",
                "expected_impact": "Every 10C reduction doubles insulation life",
                "side_effects": ["Lower current density may reduce torque"],
                "effort": "medium",
            })

        # Torque ripple
        ripple = em_results.get("torque_ripple_pct", 0)
        if ripple > 15:
            pa = params.get("Pole_Embrace", 0.78)
            suggestions.append({
                "priority": 2,
                "issue": f"Torque ripple {ripple:.1f}%",
                "action": f"Pole_Embrace {pa:.2f} -> 0.75",
                "expected_impact": "Torque ripple -20~30%",
                "side_effects": ["Torque may drop 2-3%"],
                "effort": "low",
            })

        return sorted(suggestions, key=lambda s: s["priority"])

    def check_coupling(self, param_name, current_params):
        warnings = []
        if param_name in PARAM_COUPLING:
            for related, note in PARAM_COUPLING[param_name]:
                val = current_params.get(related, "?")
                warnings.append(f"  - {related} (current: {val}): {note}")
        return warnings


# ---- Chat Engine ----
class MotorCADChat:
    """Interactive motor design conversation engine."""

    def __init__(self):
        offline = not PYMOTORCAD_AVAILABLE
        self.connector = MotorCADConnector(offline_mode=offline)
        self.analyzer = MotorAnalyzer()
        self.advisor = MotorAdvisor()
        self.proactive = ProactiveAdvisor()
        self.reporter = DesignReporter()
        self.session_mgr = SessionManager()
        self.comparator = SpecComparator()
        self.generator = InitialDesignGenerator()
        self._spec = None
        self._design = None
        self._sim_count = 0
        self._mode = "offline" if offline else "connected"

    def run(self):
        self._welcome()
        while True:
            try:
                inp = input("\nYou> ").strip()
                if not inp:
                    continue
                result = self._dispatch(inp)
                if result == "EXIT":
                    break
                elif result:
                    print(result)
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")

    def _welcome(self):
        print("=" * 60)
        print("  AI Motor Design Assistant - Chat Mode")
        print("=" * 60)
        print(f"  Mode: {self._mode}")
        if self._mode == "offline":
            print("  (Offline: changes tracked, not applied to Motor-CAD)")
        print("\n  Type 'help' for commands.")
        print("  Load a spec file or describe your project to start.")

    def _dispatch(self, text):
        t = text.lower().strip()

        if t in ("quit", "exit", "q"):
            return "EXIT"
        if t in ("help", "?"):
            return self._help()
        if t in ("status",):
            return self._status()
        if t.startswith("save"):
            p = text.split(maxsplit=1)
            return self._save(p[1] if len(p) > 1 else "session.json")
        if t.startswith("load"):
            p = text.split(maxsplit=1)
            return self._load(p[1]) if len(p) > 1 else "Usage: load <file>"
        if t in ("new",):
            return self._new()
        if t.endswith((".json", ".yaml", ".yml", ".txt", ".xlsx")):
            return self._load_spec(text)
        if t.startswith("spec:") or t.startswith("\u6307\u6807:"):
            return self._parse_spec(text.split(":", 1)[1].strip())
        if self._spec is None and any(k in t for k in ("kw", "rpm", "ipm", "spm", "\u7535\u673a", "\u6c38\u78c1", "cooling", "motor")):
            return self._parse_spec(text)
        if t in ("generate", "\u751f\u6210", "\u751f\u6210\u65b9\u6848"):
            return self._generate()
        result = self._try_param_change(text)
        if result:
            return result
        if t in ("record", "\u8bb0\u5f55", "\u8bb0\u5f55\u7ed3\u679c", "\u8bb0\u5f55\u4eff\u771f"):
            return self._record()
        if t in ("compare", "\u5bf9\u6bd4", "\u5bf9\u6bd4\u6307\u6807"):
            return self._compare()
        if t in ("suggest", "\u5efa\u8bae", "\u7ed9\u6211\u5efa\u8bae"):
            return self._suggest()
        if t == "llm" or t.startswith("llm "):
            return self._llm_analyze()
        if t.startswith("ask ") or t.startswith("\u95ee "):
            return self._llm_ask(t.split(" ", 1)[1] if " " in t else t)
        if t in ("analyze", "\u5206\u6790"):
            return self._analyze()
        if t in ("show", "\u663e\u793a", "\u5f53\u524d\u65b9\u6848", "\u67e5\u770b"):
            return self._show()
        if t in ("history", "\u5386\u53f2", "\u5386\u53f2\u8bb0\u5f55", "\u53d8\u66f4\u8bb0\u5f55"):
            return self._history()
        if t in ("undo", "\u64a4\u9500", "\u56de\u9000"):
            return self._undo()
        if t.startswith("report") or t.startswith("\u62a5\u544a"):
            p = text.split(maxsplit=1)
            return self._report(p[1] if len(p) > 1 else "")
        return f"Unknown: '{text}'. Type 'help'."

    def _help(self):
        return """
Commands:
  Spec:   <file.yaml/json/txt>   Load spec from file
          spec: <text>           Parse spec from text
          generate               Create initial design

  Change: <param> <value>       Set parameter (e.g. "Magnet_Thickness 6.5")
          <param> +<delta>       Increase (e.g. "Tooth_Width +1")
          <param> -<delta>       Decrease
          "\u9f7f\u5bbd 8"               Chinese names supported

  Sim:    record                 Log simulation results
          compare                Compare against specs
          suggest                Get proactive suggestions

  Session: save <file>           Save to file
          load <file>            Load from file
          show                   Display parameters
          history                Show change log
          undo                   Revert last change
          report [name]          Generate review report
          status                 Session overview
          help                   This help
          llm                    Deep LLM analysis of design
  ask <question>         Ask LLM a design question
  <file.xlsx>            Load spec from Excel
  quit                   Exit
"""

    def _status(self):
        lines = ["--- Session ---", f"Mode: {self._mode}"]
        s = self.session_mgr.session
        if s:
            lines += [f"Project: {s.project_name}",
                      f"Params: {len(s.parameters)}",
                      f"Changes: {len(s.change_history)}",
                      f"Sims: {len(s.snapshots)}"]
        if self._spec:
            lines.append(f"Spec: {self._spec.rated_power_kw}kW, {self._spec.rated_speed_rpm}rpm, {self._spec.motor_type}")
        return "\\n".join(lines)

    def _load_spec(self, fp):
        try:
            if fp.endswith(".xlsx"):
                from .design_spec import load_spec_from_excel
                self._spec = load_spec_from_excel(fp)
            else:
                self._spec = load_spec_from_file(fp)
            return f"Loaded: {self._spec.project_name}\\n  {self._spec.rated_power_kw}kW {self._spec.rated_speed_rpm}rpm {self._spec.motor_type}\\n  Rated torque: {self._spec.rated_torque_nm:.0f} Nm\\n\\nType 'generate' to create design."
        except Exception as e:
            return f"Failed: {e}"

    def _parse_spec(self, text):
        try:
            self._spec = parse_spec_from_text(text)
            return f"Parsed: {self._spec.project_name}\\n  {self._spec.rated_power_kw}kW {self._spec.rated_speed_rpm}rpm {self._spec.motor_type}\\n  Rated torque: {self._spec.rated_torque_nm:.0f} Nm\\n\\nType 'generate'."
        except Exception as e:
            return f"Failed: {e}"

    def _generate(self):
        if not self._spec:
            return "No spec. Load file or type requirements first."
        self.connector.connect()
        self._design = self.generator.generate(self._spec)
        dc = self._design.to_motorcad_params()
        self.session_mgr.new_session(self._spec.project_name, self._spec.__dict__, {"parameters": dc})
        for k, v in dc.items():
            self.connector.set_variable(k, v)
        d = self._design
        lines = [
            f"\\n{'='*50}",
            f"  Initial Design: {d.motor_type}",
            f"  {d.slot_number} slots / {d.pole_number} poles",
            f"  Bore: {d.stator_bore_mm:.0f}mm  Stack: {d.stack_length_mm:.0f}mm",
            f"  Airgap: {d.airgap_mm:.1f}mm  Magnet: {d.magnet_thickness_mm:.1f}mm",
            f"  Material: {d.lamination_material} / {d.magnet_material}",
            f"  Est: {d.estimated_torque_nm:.0f}Nm {d.estimated_efficiency_pct:.1f}%",
            f"{'='*50}",
            "\\nBuild this in Motor-CAD and run simulation. Then type 'record'.",
        ]
        return "\\n".join(lines)

    def _try_param_change(self, text):
        cn_set = re.match(r"(.+?)\s*(?:\u6539\u6210|\u6539\u4e3a|\u8bbe\u7f6e\u4e3a|->)\s*([\d.]+)", text)
        cn_add = re.match(r"(.+?)\s*(?:\u52a0|\u589e\u52a0|\u589e\u5927)\s*([\d.]+)", text)
        cn_sub = re.match(r"(.+?)\s*(?:\u51cf|\u51cf\u5c11|\u51cf\u5c0f|\u964d\u4f4e)\s*([\d.]+)", text)
        en_pat = re.match(r"(\w[\w\s]*?)\s+([+-]?[\d.]+)$", text)

        param_name = None
        new_value = None
        delta = 0
        is_rel = False
        name_part = ""

        if cn_set:
            name_part = cn_set.group(1).strip()
            new_value = float(cn_set.group(2))
        elif cn_add:
            name_part = cn_add.group(1).strip()
            delta = float(cn_add.group(2))
            is_rel = True
        elif cn_sub:
            name_part = cn_sub.group(1).strip()
            delta = -float(cn_sub.group(2))
            is_rel = True
        elif en_pat:
            name_part = en_pat.group(1).strip()
            vs = en_pat.group(2)
            if vs.startswith("+") or vs.startswith("-"):
                delta = float(vs)
                is_rel = True
            else:
                new_value = float(vs)
        else:
            return None

        key = name_part.lower().replace(" ", "_")
        param_name = PARAM_ALIASES.get(name_part) or PARAM_ALIASES.get(key)
        if param_name is None:
            for alias, mc_name in PARAM_ALIASES.items():
                if alias in key or key in alias:
                    param_name = mc_name
                    break
        if param_name is None:
            return None

        params = self.session_mgr.session.parameters if self.session_mgr.session else {}
        current = params.get(param_name)
        if current is None:
            return f"Parameter '{param_name}' not in design."

        if is_rel:
            new_value = current + delta
            reason = f"{name_part} {'+' if delta > 0 else ''}{delta}"
        else:
            reason = f"{name_part} -> {new_value}"

        warnings = self.proactive.check_coupling(param_name, params)
        self.connector.set_variable(param_name, new_value)
        self.session_mgr.record_change(param_name, current, new_value, reason)

        lines = [f"{param_name}: {current:.3f} -> {new_value:.3f}"]
        if self._mode == "offline":
            lines.append("  (Offline: tracked only. Update in Motor-CAD manually.)")
        if warnings:
            lines.append("  Coupling warnings:")
            lines.extend(warnings)
        return "\\n".join(lines)

    def _record(self):
        if not self.session_mgr.session:
            return "No session. Load spec and generate design first."
        self._sim_count += 1
        state = self.connector.get_full_state()
        em = state.get("em_results", {})
        thermal = state.get("thermal_results", {})
        if not any(em.values()) and not any(thermal.values()):
            return "No simulation results. Use: record torque=<val> eff=<val> ..."
        spec_dict = self._spec.__dict__ if self._spec else {}
        comp = self.comparator.compare(em, thermal, spec_dict, state.get("geometry", {}))
        self.session_mgr.record_simulation(
            f"Sim #{self._sim_count}", self.session_mgr.session.parameters, em, thermal, comp)
        sug = self.proactive.analyze_and_suggest(em, thermal, spec_dict, self.session_mgr.session.parameters, comp)
        lines = [f"\\n{'='*50}", f"  Simulation #{self._sim_count}", f"{'='*50}"]
        if em.get("torque_avg"):
            lines.append(f"  Torque: {em['torque_avg']:.1f} Nm  Eff: {em.get('efficiency', 0):.1f}%")
        if thermal.get("winding_temp_max"):
            lines.append(f"  Winding: {thermal['winding_temp_max']:.0f}C  PM: {thermal.get('pm_temp_max', 0):.0f}C")
        lines.append(f"\\n{self.comparator.format_comparison(comp)}")
        if sug:
            lines.append("\\n  Suggestions:")
            for s in sug:
                lines.append(f"\\n  [P{s['priority']}] {s['issue']}")
                lines.append(f"    Action: {s['action']}")
                lines.append(f"    Expect: {s['expected_impact']}")
        lines.append(f"\\n{'='*50}")
        return "\\n".join(lines)

    def _compare(self):
        last = self.session_mgr.get_last_snapshot()
        if not last or not last.spec_comparison:
            return "No simulation data."
        return self.comparator.format_comparison(last.spec_comparison)

    def _suggest(self):
        last = self.session_mgr.get_last_snapshot()
        if not last or not last.em_results:
            return "No simulation data."
        spec_dict = self._spec.__dict__ if self._spec else {}
        params = self.session_mgr.session.parameters if self.session_mgr.session else {}
        sug = self.proactive.analyze_and_suggest(last.em_results, last.thermal_results, spec_dict, params, last.spec_comparison)
        if not sug:
            return "All targets met!"
        lines = ["\\n--- Proactive Suggestions ---"]
        for s in sug:
            lines.append(f"\\n[P{s['priority']}] {s['issue']}")
            lines.append(f"  Action: {s['action']}")
            lines.append(f"  Expect: {s['expected_impact']}")
        return "\\n".join(lines)

    def _analyze(self):
        if not self.session_mgr.session:
            return "No session."
        state = self.connector.get_full_state()
        report = self.analyzer.analyze(state)
        return report.summary

    def _show(self):
        if not self.session_mgr.session:
            return "No session."
        params = self.session_mgr.session.parameters
        if not params:
            return "No parameters."
        keys = ["Slot_Number", "Pole_Number", "Stator_Lam_Dia", "Stator_Bore",
                 "Airgap", "Stack_Length", "Tooth_Width", "Slot_Depth",
                 "Stator_Yoke_Width", "Magnet_Thickness", "Magnet_Arc", "Pole_Embrace"]
        lines = ["\\n--- Design Parameters ---"]
        for k in keys:
            if k in params:
                lines.append(f"  {k:<20s}: {params[k]:.3f}" if isinstance(params[k], float) else f"  {k:<20s}: {params[k]}")
        return "\\n".join(lines)

    def _history(self):
        if not self.session_mgr.session:
            return "No session."
        ch = self.session_mgr.session.change_history
        if not ch:
            return "No changes."
        lines = [f"\\n--- Changes ({len(ch)} total) ---"]
        for c in ch[-15:]:
            lines.append(f"  {c}")
        return "\\n".join(lines)

    def _undo(self):
        if not self.session_mgr.session:
            return "No session."
        rec = self.session_mgr.undo()
        if rec is None:
            return "Nothing to undo."
        self.connector.set_variable(rec.parameter, rec.new_value)
        return f"Undo: {rec.parameter} -> {rec.new_value:.3f}"

    def _report(self, name=""):
        if not self.session_mgr.session:
            return "No session."
        last = self.session_mgr.get_last_snapshot()
        if not last:
            return "No simulation data."
        ds = {"geometry": self.session_mgr.session.parameters,
              "em_results": last.em_results, "thermal_results": last.thermal_results}
        report = self.analyzer.analyze(ds)
        spec_dict = self._spec.__dict__ if self._spec else {}
        raw_sug = self.proactive.analyze_and_suggest(last.em_results, last.thermal_results, spec_dict,
            self.session_mgr.session.parameters, last.spec_comparison)
        adv_sug = []
        for s in raw_sug:
            adv_sug.append(Suggestion(priority=s["priority"], category="design", title=s["issue"],
                detail=s["action"], expected_impact=s["expected_impact"],
                effort=s.get("effort","medium"), relates_to=""))
        pn = name or self.session_mgr.session.project_name
        fp = f"report_{pn.lower().replace(' ', '_')}.md"
        md = self.reporter.generate_markdown(report, adv_sug, pn, ds)
        self.reporter.save_report(md, fp)
        return f"Report saved: {fp}"

    def _llm_analyze(self):
        """Deep LLM analysis of current design."""
        last = self.session_mgr.get_last_snapshot()
        if not last:
            return "No simulation data. Record simulation first."
        
        # Build summaries
        spec_s = ""
        if self._spec:
            spec_s = f"{self._spec.rated_power_kw}kW {self._spec.rated_speed_rpm}rpm {self._spec.motor_type} {self._spec.cooling}"
        design_s = ""
        if last.em_results:
            e = last.em_results
            design_s = f"Torque: {e.get('torque_avg','?')}Nm, Eff: {e.get('efficiency','?')}%, "
            design_s += f"Ripple: {e.get('torque_ripple_pct','?')}%, "
            design_s += f"Losses: Cu={e.get('copper_loss','?')}kW Fe={e.get('iron_loss','?')}kW PM={e.get('pm_loss','?')}kW"
        if last.thermal_results:
            t = last.thermal_results
            design_s += f" | Temp: Winding={t.get('winding_temp_max','?')}C PM={t.get('pm_temp_max','?')}C"

        # Get rule-based suggestions first
        spec_dict = self._spec.__dict__ if self._spec else {}
        rule_sug = self.proactive.analyze_and_suggest(
            last.em_results, last.thermal_results, spec_dict,
            self.session_mgr.session.parameters, last.spec_comparison)
        rule_text = "\n".join([f"[P{s['priority']}] {s['issue']}: {s['action']}" for s in rule_sug])

        advisor = get_llm_advisor()
        app = self._spec.application if self._spec else "industrial"
        
        print("  (Analyzing with LLM...)")
        analysis = advisor.analyze_design(design_s, spec_s, rule_text, app)
        return f"\n{'='*50}\n  LLM Deep Analysis\n{'='*50}\n{analysis}\n{'='*50}"

    def _llm_ask(self, question: str):
        """Ask an open-ended design question to LLM."""
        if not self.session_mgr or not self.session_mgr.session:
            return "No active session."
        
        params = self.session_mgr.session.parameters
        last = self.session_mgr.get_last_snapshot()
        ctx = f"Parameters: {json.dumps({k: v for k, v in list(params.items())[:15]})}\n"
        if last and last.em_results:
            ctx += f"Results: {last.em_results}\n"
        if last and last.thermal_results:
            ctx += f"Thermal: {last.thermal_results}\n"
        
        advisor = get_llm_advisor()
        print("  (LLM thinking...)")
        return f"\n{advisor.answer_question(question, ctx)}"


    def _save(self, fp):
        if not self.session_mgr.session:
            return "No session."
        self.session_mgr.save_session(fp)
        return f"Saved: {fp}"

    def _load(self, fp):
        self.session_mgr.load_session(fp)
        s = self.session_mgr.session
        for k, v in s.parameters.items():
            try: self.connector.set_variable(k, v)
            except: pass
        return f"Loaded: {s.project_name} ({len(s.snapshots)} sims, {len(s.change_history)} changes)"

    def _new(self):
        self._spec = None
        self._design = None
        self._sim_count = 0
        self.session_mgr = SessionManager()
        return "New session ready."


def main():
    chat = MotorCADChat()
    chat.run()

if __name__ == "__main__":
    main()
