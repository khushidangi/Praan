"""Integration tests for the full pipeline."""

import pytest
from backend.simulated_probe import SimulatedProbe
from safety.rule_engine import evaluate
from pipeline.guidance import GuidanceGenerator
from pipeline.voice import VoiceGenerator


class TestFullPipeline:
    """Test the complete probe → decision → guidance → voice pipeline."""

    def test_safe_scenario_pipeline(self):
        """Test full pipeline with safe readings."""
        # Generate probe reading
        probe = SimulatedProbe(scenario="safe")
        frame = probe.read_frame()

        # Evaluate safety decision
        decision = evaluate(frame)
        assert decision["decision"] == "GO"
        assert decision["risk_tier"] == "safe"
        assert decision["provenance"]["decision_source"] == "deterministic_rule_engine"

        # Generate guidance
        guidance_gen = GuidanceGenerator(use_genie=False)
        guidance = guidance_gen.generate(decision, language="hi")
        assert "सुरक्षित" in guidance["text"] or "safe" in guidance["text"].lower()

        # Generate voice (placeholder)
        voice_gen = VoiceGenerator(language="hi")
        audio = voice_gen.synthesize(guidance["text"])
        assert len(audio) > 0

    def test_hazard_scenario_pipeline(self):
        """Test full pipeline with hazardous readings."""
        probe = SimulatedProbe(scenario="mixed_hazard")
        frame = probe.read_frame()

        decision = evaluate(frame)
        assert decision["decision"] == "NO_GO"
        assert len(decision["violated_thresholds"]) > 0

        guidance_gen = GuidanceGenerator(use_genie=False)
        guidance = guidance_gen.generate(decision, language="hi")
        assert "मत जाइए" in guidance["text"] or "not enter" in guidance["text"].lower()

    def test_sensor_fault_pipeline(self):
        """Test pipeline handles sensor faults correctly."""
        probe = SimulatedProbe(scenario="safe")
        frame = probe.read_frame()
        
        # Simulate sensor fault
        frame["sensor_status"]["h2s"] = "fault"

        decision = evaluate(frame)
        assert decision["decision"] == "UNKNOWN"
        assert decision["risk_tier"] == "unknown"

        guidance_gen = GuidanceGenerator(use_genie=False)
        guidance = guidance_gen.generate(decision, language="hi")
        assert "सेंसर" in guidance["text"] or "sensor" in guidance["text"].lower()

    def test_provenance_tracking(self):
        """Ensure provenance correctly tracks decision vs explanation sources."""
        probe = SimulatedProbe(scenario="safe")
        frame = probe.read_frame()

        decision = evaluate(frame)
        
        # Critical: LLM never decides safety
        assert decision["provenance"]["decision_source"] == "deterministic_rule_engine"
        assert decision["provenance"]["explanation_source"] == "on_device_llm"
        assert decision["provenance"]["sensors_operational"] == "4/4"

    def test_all_scenarios_produce_valid_pipeline(self):
        """Test that all simulation scenarios produce valid output."""
        scenarios = ["safe", "h2s_buildup", "o2_depletion", "sensor_fault", "mixed_hazard"]
        guidance_gen = GuidanceGenerator(use_genie=False)

        for scenario in scenarios:
            probe = SimulatedProbe(scenario=scenario)
            frame = probe.read_frame()
            
            decision = evaluate(frame)
            assert decision["decision"] in ["GO", "CAUTION", "NO_GO", "UNKNOWN"]
            
            guidance = guidance_gen.generate(decision, language="hi")
            assert len(guidance["text"]) > 0
            assert guidance["language"] == "hi"


class TestLanguageSupport:
    """Test multi-language guidance generation."""

    def test_english_guidance(self):
        """Test English guidance generation."""
        probe = SimulatedProbe(scenario="safe")
        frame = probe.read_frame()
        decision = evaluate(frame)

        guidance_gen = GuidanceGenerator(use_genie=False)
        guidance = guidance_gen.generate(decision, language="en")
        
        assert guidance["language"] == "en"
        assert "safe" in guidance["text"].lower() or "permit" in guidance["text"].lower()

    def test_hindi_guidance(self):
        """Test Hindi guidance generation."""
        probe = SimulatedProbe(scenario="mixed_hazard")
        frame = probe.read_frame()
        decision = evaluate(frame)

        guidance_gen = GuidanceGenerator(use_genie=False)
        guidance = guidance_gen.generate(decision, language="hi")
        
        assert guidance["language"] == "hi"
        # Should contain Hindi text (Devanagari script)
        assert any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in guidance["text"])


class TestSimulatedProbe:
    """Test simulated probe behavior."""

    def test_scenario_switching(self):
        """Test that scenario switching works correctly."""
        probe = SimulatedProbe(scenario="safe")
        
        # Safe scenario should have low readings
        frame = probe.read_frame()
        assert frame["h2s_ppm"] < 5.0
        
        # Switch to hazard scenario
        probe.set_scenario("mixed_hazard")
        frame = probe.read_frame()
        assert frame["h2s_ppm"] > 20.0  # Should be in hazard range

    def test_sensor_status_reporting(self):
        """Test that sensor status is correctly reported."""
        probe = SimulatedProbe(scenario="safe")
        frame = probe.read_frame()
        
        assert "sensor_status" in frame
        assert all(sensor in frame["sensor_status"] for sensor in ["h2s", "co", "o2", "lel"])
        assert all(status == "ok" for status in frame["sensor_status"].values())

    def test_sensor_fault_scenario(self):
        """Test sensor fault simulation."""
        probe = SimulatedProbe(scenario="sensor_fault")
        
        # Initially, probe starts fresh
        # Fault occurs after elapsed time > 10 seconds in the scenario
        import time
        
        # First reading should be OK (just started)
        frame1 = probe.read_frame()
        assert frame1["sensor_status"]["h2s"] == "ok"
        
        # After 11 seconds elapsed, fault should be present
        # Fast-forward by manipulating start_time
        probe.start_time = time.time() - 11
        
        frame2 = probe.read_frame()
        assert frame2["sensor_status"]["h2s"] == "fault"
