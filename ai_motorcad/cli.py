"""CLI interface for AI Motor Design Assistant.

Usage:
    python -m ai_motorcad.cli connect          # Connect to Motor-CAD
    python -m ai_motorcad.cli analyze          # Analyze current design
    python -m ai_motorcad.cli suggest          # Get improvement suggestions
    python -m ai_motorcad.cli report [name]    # Generate full design review report
    python -m ai_motorcad.cli status           # Show current design status
"""

import argparse
import sys
from pathlib import Path

from .connector import MotorCADConnector
from .analyzer import MotorAnalyzer
from .advisor import MotorAdvisor
from .reporter import DesignReporter


class MotorCADAssistant:
    """Main AI assistant orchestrator."""

    def __init__(self):
        self.connector = MotorCADConnector()
        self.analyzer = MotorAnalyzer()
        self.advisor = MotorAdvisor()
        self.reporter = DesignReporter()
        self._design_state: dict = {}
        self._report = None
        self._suggestions: list = []

    def connect(self, port: int = -1, open_new: bool = True):
        print("Connecting to Motor-CAD...")
        self.connector.connect(port=port, open_new=open_new)
        print("Connected successfully.")

    def load_design(self, filepath: str):
        self.connector.load_project(filepath)
        print(f"Loaded: {filepath}")

    def analyze(self):
        print("Extracting design state from Motor-CAD...", end=" ")
        self._design_state = self.connector.get_full_state()
        print("done.")

        print("Running analysis...", end=" ")
        self._report = self.analyzer.analyze(self._design_state)
        print("done.\n")
        print(self._report.summary)
        return self._report

    def suggest(self):
        if self._report is None:
            print("Run analyze first.", file=sys.stderr)
            return

        print("Generating suggestions...", end=" ")
        self._suggestions = self.advisor.suggest(self._report, self._design_state)
        print(f"{len(self._suggestions)} suggestions found.\n")

        pri_labels = {1: "CRIT", 2: "HIGH", 3: "MED ", 4: "LOW ", 5: "NICE"}
        for s in self._suggestions:
            print(f"[{pri_labels.get(s.priority, '?')}] {s.title}")
            print(f"       Impact: {s.expected_impact}")
            print(f"       Effort: {s.effort}\n")

        return self._suggestions

    def report(self, name: str = "Motor Design", output: str = "") -> str:
        if self._report is None:
            print("Run analyze first.", file=sys.stderr)
            return ""

        if not self._suggestions:
            self.suggest()

        md = self.reporter.generate_markdown(
            self._report, self._suggestions,
            design_name=name, design_state=self._design_state,
        )

        if output:
            self.reporter.save_report(md, output)
            print(f"Report saved to: {output}")
        else:
            output = f"design_review_{name.lower().replace(' ', '_')}.md"
            self.reporter.save_report(md, output)
            print(f"Report saved to: {output}")

        return md

    def status(self):
        print(f"Motor-CAD: {'connected' if self.connector.is_connected else 'disconnected'}")
        if self._design_state:
            geo = self._design_state.get("geometry", {})
            print(f"Design: {geo.get('Slot_Number', '?')} slots / {geo.get('Pole_Number', '?')} poles")
        if self._report:
            print(f"Last analysis score: {self._report.overall_score:.0f}/100")

    def close(self):
        if self.connector.is_connected:
            self.connector.disconnect()
            print("Disconnected from Motor-CAD.")


def main():
    parser = argparse.ArgumentParser(
        description="AI Motor Design Assistant",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("connect")
    sub.add_parser("analyze")
    sub.add_parser("suggest")

    rp = sub.add_parser("report")
    rp.add_argument("name", nargs="?", default="Motor Design")
    rp.add_argument("-o", "--output", default="")

    sub.add_parser("status")

    load = sub.add_parser("load")
    load.add_argument("filepath")

    args = parser.parse_args()
    assistant = MotorCADAssistant()

    try:
        if args.command == "connect":
            assistant.connect()
        elif args.command == "analyze":
            assistant.connect(open_new=False)
            assistant.analyze()
        elif args.command == "suggest":
            assistant.connect(open_new=False)
            assistant.analyze()
            assistant.suggest()
        elif args.command == "report":
            assistant.connect(open_new=False)
            assistant.analyze()
            assistant.report(name=args.name or "Motor Design", output=args.output)
        elif args.command == "status":
            assistant.status()
        elif args.command == "load":
            assistant.connect(open_new=False)
            assistant.load_design(args.filepath)
            assistant.status()
        else:
            parser.print_help()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    finally:
        assistant.close()


if __name__ == "__main__":
    main()