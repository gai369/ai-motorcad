"""LLM-powered deep design advisor.

Complements the rule-based ProactiveAdvisor with deep reasoning:
- Explains WHY a suggestion works (electromagnetic physics)
- Considers application context (EV vs industrial vs servo)
- Provides cost/benefit tradeoff analysis
- Answers open-ended design questions

Works via OpenAI-compatible API with offline fallback.
"""

import json
import os
import urllib.request
from typing import Optional


# ---- LLM Client (lightweight, no openai package needed) ----

class LLMClient:
    """Lightweight OpenAI-compatible API client."""

    def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1",
                 model: str = "gpt-4o", timeout: int = 30):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list, temperature: float = 0.3,
             max_tokens: int = 1500) -> str:
        """Send chat completion request."""
        if not self.api_key:
            return self._fallback_response(messages)

        data = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode())
                return result["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  (LLM unavailable: {e}, using offline analysis)")
            return self._fallback_response(messages)

    def _fallback_ask(self, question: str) -> str:
        """Offline answer for common motor design questions."""
        q = question.lower()
        lines = ["[Offline Answer - LLM unavailable]\n"]

        if "hairpin" in q or "发卡" in q:
            lines.append("**Hairpin Winding Feasibility Analysis:**\n")
            lines.append("Advantages:")
            lines.append("- Slot fill factor: 0.65-0.75 (vs 0.40-0.50 for random wound)")
            lines.append("- Better thermal conductivity: direct contact with slot wall")
            lines.append("- Shorter end-windings: 30-40% reduction in copper volume")
            lines.append("- Automated manufacturing: consistent quality\n")
            lines.append("Considerations:")
            lines.append("- Minimum slot opening: ~2.5mm for insertion tooling")
            lines.append("- AC copper loss: significant above 400-500Hz fundamental")
            lines.append("- Parallel branches needed for voltage adjustment")
            lines.append("- Design for manufacturing: bend radius, insertion clearance\n")
            lines.append("Decision criteria:")
            lines.append("- If slot fill <0.45 with round wire: hairpin worth considering")
            lines.append("- If speed >8000rpm (8-pole): check AC loss penalty")
            lines.append("- Production volume >10k/year: automation cost justified")

        elif "齿槽转矩" in q or "cogging" in q:
            lines.append("**Cogging Torque Reduction Strategies:**\n")
            lines.append("1. Slot/pole combination: fractional slot (e.g., 27s/6p) minimizes cogging")
            lines.append("2. Stator skew: one slot pitch eliminates fundamental cogging")
            lines.append("3. PM pole arc optimization: ~0.72-0.78 pole pitch minimizes 6th harmonic")
            lines.append("4. Slot opening: reduce to 2-3x airgap length")
            lines.append("5. Dummy slots/notches: add on tooth tips to increase cogging frequency")

        elif "效率" in q or "efficiency" in q:
            lines.append("**Efficiency Improvement Strategy:**\n")
            lines.append("Loss breakdown approach:")
            lines.append("1. Copper loss (I^2R): reduce current density or increase slot fill")
            lines.append("2. Iron loss: thinner laminations (0.35->0.20mm = -30% eddy loss)")
            lines.append("3. PM eddy loss: segment magnets (3-5 circumferential segments)")
            lines.append("4. Windage: smooth rotor surface, optimize airgap")
            lines.append("5. AC loss: minimize strand diameter at high frequency\n")
            lines.append("IE4/IE5 targets:")
            lines.append("- IE4: typically 0.20mm laminations + optimized magnetics")
            lines.append("- IE5: may require amorphous metal or 6.5% Si steel")

        elif "散热" in q or "冷却" in q or "thermal" in q or "cooling" in q:
            lines.append("**Cooling System Design:**\n")
            lines.append("Cooling capacity comparison:")
            lines.append("- Natural convection: 3-8 A/mm^2 current density")
            lines.append("- Forced air (finned housing): 8-15 A/mm^2")
            lines.append("- Water jacket: 15-25 A/mm^2")
            lines.append("- Oil spray: 20-30 A/mm^2")
            lines.append("- Oil immersion: 25-35 A/mm^2\n")
            lines.append("Key considerations:")
            lines.append("- Winding hotspot: typically 15-25C above average")
            lines.append("- PM temperature: critical for demagnetization margin")
            lines.append("- Thermal time constant: 10-60min depending on size")

        else:
            lines.append("This question requires LLM analysis. Set OPENAI_API_KEY for full capability.")
            lines.append("\nGeneral design approach:")
            lines.append("- Start with electromagnetic sizing (D^2L from torque)")
            lines.append("- Verify flux densities below saturation limits")
            lines.append("- Check thermal limits for your cooling method")
            lines.append("- Iterate: magnetic -> electric -> thermal -> mechanical")

        return "\n".join(lines)


    def _fallback_response(self, messages: list) -> str:
        """Generate intelligent offline analysis without API call."""
        user_msg = ""
        for m in messages:
            if m["role"] == "user":
                user_msg = m["content"]
                break

        # Check if this is a direct question (ask mode)
        if user_msg.startswith("Context:"):
            question = user_msg.split("Question:")[-1].strip() if "Question:" in user_msg else ""
            return self._fallback_ask(question)

        # Extract key info
        torque_ok = "torque meets target" in user_msg.lower()
        eff_ok = "efficiency meets target" in user_msg.lower()

        lines = ["[Offline Analysis - LLM unavailable]\n"]

        # Application-aware reasoning
        if "traction" in user_msg.lower() or "ev" in user_msg.lower():
            lines.append("**Application Context (EV Traction):**")
            lines.append("- Priority: torque density > efficiency > NVH")
            lines.append("- Wide speed range required (field weakening capability is key)")
            lines.append("- PM segmentation recommended for high-speed loss reduction")
            lines.append("- Hairpin winding worth considering for >0.65 slot fill factor")
        elif "industrial" in user_msg.lower():
            lines.append("**Application Context (Industrial):**")
            lines.append("- Priority: efficiency > reliability > cost")
            lines.append("- IE4/IE5 compliance may drive lamination grade choice")
            lines.append("- Consider cast copper rotor if induction motor variant")
        elif "servo" in user_msg.lower():
            lines.append("**Application Context (Servo):**")
            lines.append("- Priority: torque ripple < inertia < response time")
            lines.append("- Low cogging design: consider fractional slot, closed slots")
            lines.append("- High slot fill factor reduces thermal time constant")

        # Physics reasoning
        lines.append("\n**Electromagnetic Analysis:**")
        if not torque_ok:
            lines.append("- Torque deficit: check if magnetic loading (airgap B) or electric loading (current density) is the bottleneck")
            lines.append("- Airgap flux density below 0.85T: PM strength or thickness insufficient")
            lines.append("- If electric loading limited: increase slot area or improve cooling")

        if not eff_ok:
            lines.append("- Efficiency gap analysis by loss component:")
            lines.append("  - Copper loss: proportional to current density squared. Halving current density cuts copper loss by 75%")
            lines.append("  - Iron loss: proportional to frequency^1.5 and flux density^2. Thin laminations (0.20mm) reduce eddy current loss")
            lines.append("  - PM eddy loss: proportional to (slot opening/airgap)^2. Closing slots helps significantly")

        lines.append("\n**Design Optimization Strategy:**")
        lines.append("1. First fix magnetic circuit (saturation, flux density)")
        lines.append("2. Then optimize electric loading (current density, fill factor)")
        lines.append("3. Finally fine-tune for NVH (torque ripple, cogging, radial forces)")

        lines.append("\n**Risk Assessment:**")
        lines.append("- Demagnetization: verify PM operating point at max current and max temperature")
        lines.append("- Mechanical: check rotor stress at overspeed (typically 1.2x max speed)")
        lines.append("- Thermal: verify winding hotspot stays within insulation class limit")

        return "\n".join(lines)


# ---- LLM Advisor ----

class LLMAdvisor:
    """Deep design advisor powered by LLM reasoning."""

    SYSTEM_PROMPT = """You are a senior motor electromagnetic design expert with 20+ years of experience. 
You specialize in permanent magnet synchronous motors (IPM/SPM) for EV traction, industrial, and servo applications.

When analyzing a motor design:
1. Apply electromagnetic physics principles to explain root causes
2. Consider the specific application context (EV vs industrial vs servo)
3. Provide quantified improvement suggestions with expected impact
4. Warn about side effects and coupling parameters
5. Use Chinese when the input is in Chinese, English otherwise
6. Be concise but thorough - engineers value precision over verbosity

Your analysis should cover: magnetic circuit, electric loading, loss breakdown, thermal, mechanical, and NVH aspects."""

    def __init__(self, api_key: str = "", model: str = "gpt-4o"):
        self.client = LLMClient(api_key=api_key, model=model)

    def analyze_design(self, design_summary: str, spec_summary: str,
                       rule_suggestions: str, application: str = "industrial") -> str:
        """Generate deep analysis of a motor design.

        Args:
            design_summary: Summary of current design state.
            spec_summary: Project specification summary.
            rule_suggestions: Suggestions from rule-based engine.
            application: Application context.

        Returns:
            Detailed LLM analysis text.
        """
        user_prompt = f"""Please analyze this motor design:

**Project Specification:**
{spec_summary}

**Current Design & Simulation Results:**
{design_summary}

**Rule-based Suggestions (for reference):**
{rule_suggestions}

**Application:** {application}

Please provide:
1. Root cause analysis of any issues found
2. Prioritized improvement recommendations with specific parameter changes
3. Cost-benefit tradeoff for each recommendation
4. Risks and side effects to watch for
5. Next simulation step recommendation

Be specific with numbers and parameter names."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        return self.client.chat(messages)

    def answer_question(self, question: str, context: str) -> str:
        """Answer an open-ended design question with context.

        Args:
            question: User's design question.
            context: Current design state and history.

        Returns:
            LLM response.
        """
        user_prompt = f"""Context:
{context}

Question: {question}

Please provide a detailed, technically accurate answer grounded in electromagnetic design principles."""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        return self.client.chat(messages)

    def review_changes(self, changes: str, context: str) -> str:
        """Review proposed parameter changes and predict impact.

        Args:
            changes: Description of proposed changes.
            context: Current design state.

        Returns:
            Predicted impact analysis.
        """
        user_prompt = f"""Current design state:
{context}

Proposed changes:
{changes}

Please predict:
1. Expected impact on torque, efficiency, temperatures, ripple
2. Any potential issues or coupling effects
3. Whether these changes are advisable and why"""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        return self.client.chat(messages)


# ---- Convenience functions ----

_llm_instance: Optional[LLMAdvisor] = None


def get_llm_advisor(api_key: str = "") -> LLMAdvisor:
    """Get or create the global LLM advisor instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMAdvisor(api_key=api_key)
    return _llm_instance


def has_llm() -> bool:
    """Check if LLM API key is configured."""
    return bool(os.environ.get("OPENAI_API_KEY", ""))
