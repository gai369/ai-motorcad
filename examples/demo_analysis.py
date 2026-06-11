"""Demo: AI Motor Design Assistant - offline analysis example.

This demo shows how to use the assistant without a live Motor-CAD connection.
You can manually provide design parameters for analysis.
"""

from ai_motorcad.analyzer import MotorAnalyzer
from ai_motorcad.advisor import MotorAdvisor
from ai_motorcad.reporter import DesignReporter


def main():
    """Analyze a sample IPM traction motor design."""

    # Sample design state (normally comes from MotorCADConnector.get_full_state())
    design_state = {
        "geometry": {
            "Stator_Lam_Dia": 220.0,
            "Stator_Bore": 150.0,
            "Airgap": 1.0,
            "Stack_Length": 140.0,
            "Slot_Number": 48,
            "Pole_Number": 8,
            "Tooth_Width": 6.5,
            "Slot_Depth": 25.0,
            "Stator_Yoke_Width": 15.0,
            "Magnet_Thickness": 6.0,
            "Magnet_Arc": 140.0,
            "Pole_Embrace": 0.78,
        },
        "materials": {
            "Stator_Lam_Material": "M250-35A",
            "Magnet_Material": "NdFeB_42UH",
        },
        "em_results": {
            "torque_avg": 480.0,
            "torque_ripple_pct": 12.5,
            "cogging_torque": 8.0,
            "efficiency": 94.2,
            "airgap_flux_density": 0.92,
            "tooth_flux_density": 1.75,
            "yoke_flux_density": 1.45,
            "current_density_rms": 14.0,
            "total_loss": 8.7,
            "copper_loss": 3.8,
            "iron_loss": 3.2,
            "pm_loss": 1.5,
        },
        "thermal_results": {
            "winding_temp_max": 155.0,
            "pm_temp_max": 135.0,
            "stator_temp_max": 140.0,
        },
    }

    print("=" * 60)
    print("AI Motor Design Assistant - Demo Analysis")
    print("=" * 60)
    print()
    print("Design: 150kW EV Traction IPM Motor")
    print(f"  {design_state['geometry']['Slot_Number']} slots / {design_state['geometry']['Pole_Number']} poles")
    print(f"  Rated torque: {design_state['em_results']['torque_avg']} Nm")
    print()

    # Step 1: Analyze
    print("Running analysis...")
    analyzer = MotorAnalyzer()
    report = analyzer.analyze(design_state)
    print(report.summary)
    print()

    # Step 2: Get suggestions
    print("Generating improvement suggestions...")
    advisor = MotorAdvisor()
    suggestions = advisor.suggest(report, design_state)

    for s in suggestions:
        pri = {1: "P1", 2: "P2", 3: "P3", 4: "P4", 5: "P5"}
        print(f"  [{pri.get(s.priority, '?')}] {s.title}")
        print(f"      Impact: {s.expected_impact} | Effort: {s.effort}")
    print()

    # Step 3: Generate report
    print("Generating design review report...")
    reporter = DesignReporter()
    md = reporter.generate_markdown(report, suggestions, "150kW EV Traction Motor", design_state)
    reporter.save_report(md, "design_review_demo.md")
    print("Report saved to: design_review_demo.md")
    print()

    # Step 4: Show report preview
    print("Report preview (first 30 lines):")
    print("-" * 40)
    for line in md.split("\n")[:30]:
        print(line)


if __name__ == "__main__":
    main()