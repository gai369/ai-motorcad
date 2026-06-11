"""Chat Mode Demo - Interactive motor design assistant (offline).

This demo shows the complete chat workflow without needing Motor-CAD.
It automates a typical design iteration:
1. Load project spec from YAML file
2. Generate initial design
3. Modify parameters via natural language
4. Record simulation results
5. Get proactive suggestions
"""

from ai_motorcad.chat import MotorCADChat
from ai_motorcad.design_spec import load_spec_from_file
from ai_motorcad.connector import MotorCADConnector


def main():
    """Run automated demo of the chat workflow."""
    chat = MotorCADChat()
    # Force offline mode (no Motor-CAD needed for demo)
    chat.connector._offline_mode = True
    chat._mode = "offline"
    chat.connector.connect()

    print("=" * 60)
    print("  DEMO: AI Motor Design Assistant - Chat Workflow")
    print("  Mode: OFFLINE (no Motor-CAD required)")
    print("=" * 60)
    print()

    # Step 1: Load spec from YAML file
    print("Step 1: Loading project spec from sample_spec.yaml...")
    result = chat._load_spec("examples/sample_spec.yaml")
    print(result)
    print()

    # Step 2: Generate initial design
    print("Step 2: Generating initial design...")
    result = chat._generate()
    print(result)
    print()

    # Step 3: Modify parameters via natural language
    print("Step 3: User modifies parameters via natural language...")
    changes = [
        ("Magnet_Thickness 6.5", "User: magnet thickness 6.5"),
        ("Tooth_Width +1", "User: widen teeth by 1mm"),
        (chr(40831)+chr(23485)+" 8", "User: tooth width 8 (Chinese)"),
    ]
    for cmd_text, desc in changes:
        print(f"  Command: {cmd_text}  ({desc})")
        result = chat._try_param_change(cmd_text)
        print(f"  {result}")
        print()

    # Step 4: Set simulated results and record
    print("Step 4: Setting simulated results and recording...")
    chat.connector.set_simulated_results(
        em={
            "torque_avg": 365.0, "torque_ripple_pct": 8.5,
            "efficiency": 94.3, "airgap_flux_density": 0.88,
            "tooth_flux_density": 1.62, "yoke_flux_density": 1.38,
            "copper_loss": 4.2, "iron_loss": 3.8,
            "pm_loss": 1.2, "total_loss": 9.2,
        },
        thermal={"winding_temp_max": 152.0, "pm_temp_max": 138.0},
    )

    result = chat._record()
    print(result)
    print()

    # Step 5: Session summary
    print("Step 5: Session summary...")
    print(chat._status())
    print()
    print(chat._show())
    print()

    # Step 6: Generate report
    print("Step 6: Generating design review report...")
    result = chat._report()
    print(result)
    print()

    print("=" * 60)
    print("  Demo complete!")
    print("  Report saved. Run 'python -m ai_motorcad.chat' for interactive mode.")
    print("=" * 60)


if __name__ == "__main__":
    main()
