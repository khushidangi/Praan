"""Guidance generation pipeline.

Translates rule-engine safety decisions into plain-language instructions
using an on-device LLM (Llama-3.2-3B-Instruct via Qualcomm Genie).

CRITICAL: The LLM NEVER makes the safety decision. It only explains a decision
that the deterministic rule engine has already made.
"""

import json
from typing import Dict, Optional
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You translate a safety decision into one short, clear instruction.
You do not make the decision — it has already been made.
Never contradict the decision given to you.
Never add reassurance the decision does not support.
Output at most two sentences."""


LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (हिंदी)",
}


def build_prompt(rule_decision: Dict, language: str = "hi") -> str:
    """Build the LLM prompt from a rule-engine decision.

    Args:
        rule_decision: Output from safety.rule_engine.evaluate()
        language: Target language code (currently: "en", "hi")

    Returns:
        Complete prompt string ready for LLM inference
    """
    lang_name = LANGUAGE_NAMES.get(language, "English")

    decision = rule_decision["decision"]
    risk_tier = rule_decision["risk_tier"]
    violated = rule_decision.get("violated_thresholds", [])

    # Format violated thresholds in human-readable form
    if violated:
        violation_str = ", ".join(violated)
    else:
        violation_str = "none"

    prompt = f"""{SYSTEM_PROMPT}

Decision: {decision}
Risk tier: {risk_tier}
Reason: {violation_str}

Respond in {lang_name}. Keep it short and direct."""

    return prompt


# ──────────────────────────────────────────────────────────────────────
# Genie integration (placeholder for now)
# ──────────────────────────────────────────────────────────────────────

class GuidanceGenerator:
    """Wraps the Genie LLM inference for guidance generation.

    TODO: Integrate actual Genie runtime when model is compiled.
    For now, uses rule-based fallback templates.
    """

    def __init__(self, genie_bundle_path: Optional[Path] = None, use_genie: bool = False):
        """Initialize guidance generator.

        Args:
            genie_bundle_path: Path to compiled Genie bundle (context binaries + config)
            use_genie: If True, use actual Genie inference; else use templates
        """
        self.genie_bundle_path = genie_bundle_path
        self.use_genie = use_genie

        if use_genie and genie_bundle_path:
            self._init_genie()
        else:
            print("[GuidanceGenerator] Using template-based fallback (Genie not available)")

    def _init_genie(self):
        """Initialize Genie runtime (placeholder)."""
        # TODO: Load Genie model
        # from qai_appbuilder import QNNContext
        # self.model = QNNContext(str(self.genie_bundle_path))
        pass

    def generate(self, rule_decision: Dict, language: str = "hi") -> Dict:
        """Generate guidance message from a rule-engine decision.

        Args:
            rule_decision: Output from safety.rule_engine.evaluate()
            language: Target language code

        Returns:
            Guidance message dict with keys: ts, language, text, audio_ready
        """
        if self.use_genie:
            # TODO: Call Genie inference
            # prompt = build_prompt(rule_decision, language)
            # text = self.model.generate(prompt, max_tokens=50)
            text = self._template_fallback(rule_decision, language)
        else:
            text = self._template_fallback(rule_decision, language)

        return {
            "ts": rule_decision.get("ts", 0),
            "language": language,
            "text": text,
            "audio_ready": False,  # Will be set to True after TTS
        }

    def _template_fallback(self, rule_decision: Dict, language: str) -> str:
        """Template-based guidance (used when Genie not available)."""
        decision = rule_decision["decision"]
        risk_tier = rule_decision["risk_tier"]
        violated = rule_decision.get("violated_thresholds", [])

        # English templates
        if language == "en":
            if decision == "GO":
                return "Atmosphere verified safe. Entry permitted."
            elif decision == "CAUTION":
                gases = ", ".join(violated) if violated else "readings"
                return f"Caution: {gases} approaching threshold. Re-test before proceeding."
            elif decision == "NO_GO":
                gases = ", ".join(violated) if violated else "hazardous conditions"
                return f"Do not enter. Hazardous levels detected: {gases}. Notify supervisor immediately."
            elif decision == "UNKNOWN":
                return "Cannot verify atmosphere. Sensor fault detected. Do not enter until equipment is checked."

        # Hindi templates
        elif language == "hi":
            if decision == "GO":
                return "वायु सुरक्षित है। प्रवेश की अनुमति है।"
            elif decision == "CAUTION":
                return "सावधान: गैस स्तर सीमा के पास है। फिर से जाँच करें।"
            elif decision == "NO_GO":
                if "h2s_ppm" in violated:
                    return "अंदर मत जाइए। H₂S खतरनाक स्तर पर है। तुरंत सुपरवाइज़र को सूचित करें।"
                elif "o2_pct" in violated:
                    return "अंदर मत जाइए। ऑक्सीजन की कमी है। तुरंत सुपरवाइज़र को सूचित करें।"
                else:
                    return "अंदर मत जाइए। खतरनाक गैस का पता चला है। सुपरवाइज़र को सूचित करें।"
            elif decision == "UNKNOWN":
                return "सेंसर में खराबी है। प्रवेश न करें। उपकरण की जाँच करवाएं।"

        return "System error."


# ──────────────────────────────────────────────────────────────────────
# CLI testing interface
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test guidance generation")
    parser.add_argument("--language", choices=["en", "hi"], default="hi")
    args = parser.parse_args()

    generator = GuidanceGenerator(use_genie=False)

    # Test cases
    test_decisions = [
        {
            "ts": 0,
            "decision": "GO",
            "risk_tier": "safe",
            "violated_thresholds": [],
        },
        {
            "ts": 0,
            "decision": "CAUTION",
            "risk_tier": "caution",
            "violated_thresholds": ["h2s_ppm"],
        },
        {
            "ts": 0,
            "decision": "NO_GO",
            "risk_tier": "hazard",
            "violated_thresholds": ["h2s_ppm", "o2_pct"],
        },
        {
            "ts": 0,
            "decision": "UNKNOWN",
            "risk_tier": "unknown",
            "violated_thresholds": ["h2s_fault"],
        },
    ]

    for decision in test_decisions:
        guidance = generator.generate(decision, language=args.language)
        print(f"\n{decision['decision']} → {guidance['text']}")
