"""AI Motor Design Assistant - Your intelligent copilot for motor electromagnetic design.

Provides:
- Motor-CAD project connection and automation (connector)
- Electromagnetic design knowledge base (knowledge)
- Simulation result analysis with actionable insights (analyzer)
- Rule-based design suggestions (advisor)
- Project spec parsing and initial design generation (design_spec)
- Session tracking and spec comparison (design_tracker)
- Interactive chat-based design workflow (chat)
- Automatic design review report generation (reporter)
"""

__version__ = "0.2.0"

from .connector import MotorCADConnector, PYMOTORCAD_AVAILABLE
from .analyzer import MotorAnalyzer, DesignReport, Severity
from .advisor import MotorAdvisor, Suggestion
from .reporter import DesignReporter
from .design_spec import (
    ProjectSpec, InitialDesign, InitialDesignGenerator,
    load_spec_from_file, parse_spec_from_text,
)
from .design_tracker import SessionManager, SpecComparator, DesignSnapshot
from .chat import MotorCADChat, ProactiveAdvisor
from .llm_advisor import LLMAdvisor, LLMClient, get_llm_advisor, has_llm

__all__ = [
    "MotorCADConnector", "PYMOTORCAD_AVAILABLE",
    "MotorAnalyzer", "DesignReport", "Severity",
    "MotorAdvisor", "Suggestion",
    "DesignReporter",
    "ProjectSpec", "InitialDesign", "InitialDesignGenerator",
    "load_spec_from_file", "parse_spec_from_text",
    "SessionManager", "SpecComparator", "DesignSnapshot",
    "MotorCADChat", "ProactiveAdvisor",
    "LLMAdvisor", "LLMClient", "get_llm_advisor", "has_llm",
]
