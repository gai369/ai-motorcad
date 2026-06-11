"""Chat Mode Demo - Excel import + LLM analysis.

Demonstrates:
1. Loading project specs from Excel file
2. Natural language parameter modification
3. Simulation result recording with rule-based suggestions
4. LLM deep analysis (offline fallback when no API key)
"""

from ai_motorcad.chat import MotorCADChat


def main():
    chat = MotorCADChat()
    chat.connector._offline_mode = True
    chat._mode = "offline"
    chat.connector.connect()

    print("=" * 60)
    print("  DEMO: AI Motor Design Assistant")
    print("  Excel Import + LLM Analysis")
    print("=" * 60)
    print()

    # ---- Part 1: Excel Import ----
    print("Part 1: Loading spec from Excel file...")
    print("  File: examples/sample_specs.xlsx (3 motor specs)")
    result = chat._load_spec("examples/sample_specs.xlsx")
    print(result)
    print()

    # ---- Part 2: Generate Design ----
    print("Part 2: Generating initial design...")
    result = chat._generate()
    print(result)
    print()

    # ---- Part 3: Modify Parameters ----
    print("Part 3: Modifying parameters...")
    for cmd in ["磁钢厚度 6.5", "齿宽 8", "轭宽 12"]:
        r = chat._try_param_change(cmd)
        print(f"  {r}")
    print()

    # ---- Part 4: Simulate & Record ----
    print("Part 4: Recording simulation...")
    chat.connector.set_simulated_results(
        em={
            "torque_avg": 362.0, "torque_ripple_pct": 7.5, "efficiency": 94.5,
            "airgap_flux_density": 0.89, "tooth_flux_density": 1.58,
            "yoke_flux_density": 1.32, "copper_loss": 4.5, "iron_loss": 3.0,
            "pm_loss": 1.0, "total_loss": 8.5,
        },
        thermal={"winding_temp_max": 148.0, "pm_temp_max": 132.0},
    )
    result = chat._record()
    print(result)
    print()

    # ---- Part 5: LLM Deep Analysis ----
    print("Part 5: LLM deep analysis...")
    result = chat._llm_analyze()
    print(result)
    print()

    # ---- Part 6: Ask LLM a question ----
    print("Part 6: Asking LLM a design question...")
    result = chat._llm_ask("这个设计适合改成hairpin绕组吗？需要考虑哪些问题？")
    print(result)
    print()

    # ---- Summary ----
    print("=" * 60)
    print("  Session Summary")
    print(chat._status())
    print("=" * 60)


if __name__ == "__main__":
    main()
