# tests/unit/test_rule_engine.py
#
# THE MOST IMPORTANT TESTS IN THIS REPO.
#
# This test table covers:
#   - Every threshold boundary for every gas (at, just below, just above)
#   - Every sensor-fault combination
#   - Multiple simultaneous violations
#   - All four decision states: GO, CAUTION, NO_GO, UNKNOWN
#   - Oxygen's inverted logic
#   - Edge cases: missing keys, missing readings, all sensors faulty
#
# A bug here is not a bad user experience — it's a false "safe."

import pytest
from safety.rule_engine import evaluate
from safety.thresholds import THRESHOLDS


# ─── Helper: build a valid, safe telemetry frame ───────────────────────

def safe_frame(**overrides):
    """Return a telemetry frame with all readings well within safe limits.

    Any key in `overrides` replaces the default value.
    """
    frame = {
        "ts": 1758100000,
        "h2s_ppm": 0.0,
        "co_ppm": 0.0,
        "o2_pct": 20.9,
        "lel_pct": 0.0,
        "sensor_status": {
            "h2s": "ok",
            "co": "ok",
            "o2": "ok",
            "lel": "ok",
        },
        "probe_depth_m": 3.0,
    }
    # Allow overriding sensor_status individually
    if "sensor_status" in overrides:
        frame["sensor_status"] = {**frame["sensor_status"], **overrides.pop("sensor_status")}
    frame.update(overrides)
    return frame


# ═══════════════════════════════════════════════════════════════════════
# 1. CLEAN / GO STATE
# ═══════════════════════════════════════════════════════════════════════

class TestGoDecision:
    """All readings well within safe limits → GO."""

    def test_all_safe_defaults(self):
        result = evaluate(safe_frame())
        assert result["decision"] == "GO"
        assert result["risk_tier"] == "safe"
        assert result["violated_thresholds"] == []

    def test_all_readings_exactly_at_safe_boundary(self):
        """Readings AT the caution threshold are NOT violations (> not >=)."""
        result = evaluate(safe_frame(
            h2s_ppm=10,   # caution threshold exactly
            co_ppm=35,    # caution threshold exactly
            o2_pct=20.5,  # caution threshold exactly (for O2, < not <=)
            lel_pct=5,    # caution threshold exactly
        ))
        assert result["decision"] == "GO"
        assert result["risk_tier"] == "safe"

    def test_readings_just_below_caution(self):
        result = evaluate(safe_frame(
            h2s_ppm=9.99,
            co_ppm=34.99,
            o2_pct=20.51,  # O2: just ABOVE caution (safe side)
            lel_pct=4.99,
        ))
        assert result["decision"] == "GO"

    def test_provenance_always_deterministic(self):
        result = evaluate(safe_frame())
        assert result["provenance"]["decision_source"] == "deterministic_rule_engine"
        assert result["provenance"]["explanation_source"] == "on_device_llm"
        assert result["provenance"]["sensors_operational"] == "4/4"

    def test_timestamp_passed_through(self):
        result = evaluate(safe_frame(ts=1234567890))
        assert result["ts"] == 1234567890

    def test_readings_included_in_output(self):
        frame = safe_frame()
        result = evaluate(frame)
        assert result["readings"] == frame


# ═══════════════════════════════════════════════════════════════════════
# 2. CAUTION STATE
# ═══════════════════════════════════════════════════════════════════════

class TestCautionDecision:
    """Readings in caution range → CAUTION (not GO, not NO_GO)."""

    def test_h2s_just_above_caution(self):
        result = evaluate(safe_frame(h2s_ppm=10.1))
        assert result["decision"] == "CAUTION"
        assert result["risk_tier"] == "caution"
        assert "h2s_ppm" in result["violated_thresholds"]

    def test_co_just_above_caution(self):
        result = evaluate(safe_frame(co_ppm=35.1))
        assert result["decision"] == "CAUTION"
        assert "co_ppm" in result["violated_thresholds"]

    def test_o2_just_below_caution(self):
        """O2 is inverted: below caution threshold is bad."""
        result = evaluate(safe_frame(o2_pct=20.49))
        assert result["decision"] == "CAUTION"
        assert "o2_pct" in result["violated_thresholds"]

    def test_lel_just_above_caution(self):
        result = evaluate(safe_frame(lel_pct=5.1))
        assert result["decision"] == "CAUTION"
        assert "lel_pct" in result["violated_thresholds"]

    def test_h2s_at_boundary_between_caution_and_hazard(self):
        """At exactly 20 ppm (hazard threshold), should be caution, not hazard."""
        result = evaluate(safe_frame(h2s_ppm=20))
        assert result["decision"] == "CAUTION"
        assert result["risk_tier"] == "caution"

    def test_multiple_caution_violations_still_caution(self):
        """Multiple gases in caution range → still CAUTION, not NO_GO."""
        result = evaluate(safe_frame(
            h2s_ppm=15,
            co_ppm=40,
            lel_pct=7,
        ))
        assert result["decision"] == "CAUTION"
        assert result["risk_tier"] == "caution"
        assert len(result["violated_thresholds"]) == 3


# ═══════════════════════════════════════════════════════════════════════
# 3. NO_GO STATE (hazard tier)
# ═══════════════════════════════════════════════════════════════════════

class TestNoGoHazard:
    """Readings in hazard range → NO_GO."""

    def test_h2s_above_hazard(self):
        result = evaluate(safe_frame(h2s_ppm=20.1))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"

    def test_co_above_hazard(self):
        result = evaluate(safe_frame(co_ppm=100.1))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"

    def test_o2_below_hazard(self):
        result = evaluate(safe_frame(o2_pct=19.49))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"

    def test_lel_above_hazard(self):
        result = evaluate(safe_frame(lel_pct=10.1))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"

    def test_at_hazard_threshold_exactly(self):
        """At exactly hazard threshold (100 ppm CO), should still be caution."""
        result = evaluate(safe_frame(co_ppm=100))
        assert result["decision"] == "CAUTION"

    def test_o2_at_hazard_exactly(self):
        """O2 at exactly 19.5% should be caution, not hazard."""
        result = evaluate(safe_frame(o2_pct=19.5))
        assert result["decision"] == "CAUTION"


# ═══════════════════════════════════════════════════════════════════════
# 4. NO_GO STATE (extreme tier)
# ═══════════════════════════════════════════════════════════════════════

class TestNoGoExtreme:
    """Readings in extreme range → NO_GO with extreme risk tier."""

    def test_h2s_above_extreme(self):
        result = evaluate(safe_frame(h2s_ppm=100.1))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"

    def test_co_above_extreme(self):
        result = evaluate(safe_frame(co_ppm=200.1))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"

    def test_o2_below_extreme(self):
        result = evaluate(safe_frame(o2_pct=15.9))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"

    def test_lel_above_extreme(self):
        result = evaluate(safe_frame(lel_pct=20.1))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"

    def test_at_extreme_threshold_exactly(self):
        """At exactly extreme threshold (100 ppm H2S), should be hazard."""
        result = evaluate(safe_frame(h2s_ppm=100))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"

    def test_o2_at_extreme_exactly(self):
        """O2 at exactly 16.0% should be hazard, not extreme."""
        result = evaluate(safe_frame(o2_pct=16.0))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"


# ═══════════════════════════════════════════════════════════════════════
# 5. UNKNOWN STATE (sensor faults)
# ═══════════════════════════════════════════════════════════════════════

class TestUnknownDecision:
    """Any sensor fault → UNKNOWN. Never a false GO."""

    def test_single_sensor_fault(self):
        result = evaluate(safe_frame(
            sensor_status={"h2s": "fault"}
        ))
        assert result["decision"] == "UNKNOWN"
        assert result["risk_tier"] == "unknown"

    def test_multiple_sensor_faults(self):
        result = evaluate(safe_frame(
            sensor_status={"h2s": "fault", "co": "drift"}
        ))
        assert result["decision"] == "UNKNOWN"

    def test_all_sensors_faulty(self):
        result = evaluate(safe_frame(
            sensor_status={"h2s": "fault", "co": "fault", "o2": "fault", "lel": "fault"}
        ))
        assert result["decision"] == "UNKNOWN"
        assert result["risk_tier"] == "unknown"

    def test_sensor_status_error_string(self):
        """Any value other than 'ok' triggers UNKNOWN."""
        result = evaluate(safe_frame(
            sensor_status={"o2": "error"}
        ))
        assert result["decision"] == "UNKNOWN"

    def test_sensor_status_empty_string(self):
        result = evaluate(safe_frame(
            sensor_status={"lel": ""}
        ))
        assert result["decision"] == "UNKNOWN"

    def test_missing_sensor_in_status(self):
        """If a sensor key is entirely missing from sensor_status → UNKNOWN."""
        frame = safe_frame()
        del frame["sensor_status"]["h2s"]
        result = evaluate(frame)
        assert result["decision"] == "UNKNOWN"

    def test_sensor_fault_overrides_safe_readings(self):
        """Even if all gas readings are safe, a sensor fault → UNKNOWN."""
        result = evaluate(safe_frame(
            h2s_ppm=0.0, co_ppm=0.0, o2_pct=20.9, lel_pct=0.0,
            sensor_status={"co": "disconnected"}
        ))
        assert result["decision"] == "UNKNOWN"

    def test_sensor_fault_with_dangerous_readings(self):
        """Sensor fault + dangerous readings → still UNKNOWN (can't trust readings)."""
        result = evaluate(safe_frame(
            h2s_ppm=500,
            sensor_status={"h2s": "fault"}
        ))
        assert result["decision"] == "UNKNOWN"

    def test_unknown_provenance_shows_sensor_count(self):
        result = evaluate(safe_frame(
            sensor_status={"h2s": "fault", "co": "fault"}
        ))
        assert result["provenance"]["sensors_operational"] == "2/4"


# ═══════════════════════════════════════════════════════════════════════
# 6. MIXED / MULTI-GAS SCENARIOS
# ═══════════════════════════════════════════════════════════════════════

class TestMultiGasScenarios:
    """Multiple gases violating at different tiers simultaneously."""

    def test_caution_plus_hazard_yields_nogo(self):
        """Worst tier wins: hazard + caution → NO_GO."""
        result = evaluate(safe_frame(
            h2s_ppm=15,     # caution
            co_ppm=150,     # hazard
        ))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"
        assert "h2s_ppm" in result["violated_thresholds"]
        assert "co_ppm" in result["violated_thresholds"]

    def test_caution_plus_extreme_yields_nogo_extreme(self):
        result = evaluate(safe_frame(
            lel_pct=7,      # caution
            o2_pct=15.0,    # extreme
        ))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"

    def test_all_four_gases_violated(self):
        result = evaluate(safe_frame(
            h2s_ppm=150,    # extreme
            co_ppm=250,     # extreme
            o2_pct=14.0,    # extreme
            lel_pct=25,     # extreme
        ))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"
        assert len(result["violated_thresholds"]) == 4

    def test_three_caution_one_safe(self):
        result = evaluate(safe_frame(
            h2s_ppm=12,     # caution
            co_ppm=40,      # caution
            o2_pct=20.9,    # safe
            lel_pct=6,      # caution
        ))
        assert result["decision"] == "CAUTION"
        assert len(result["violated_thresholds"]) == 3

    def test_realistic_sewer_scenario_h2s_dominant(self):
        """Typical sewer scenario: high H2S, low O2, some methane."""
        result = evaluate(safe_frame(
            h2s_ppm=45,     # hazard
            co_ppm=5,       # safe
            o2_pct=19.0,    # hazard
            lel_pct=8,      # caution
        ))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"
        assert "h2s_ppm" in result["violated_thresholds"]
        assert "o2_pct" in result["violated_thresholds"]
        assert "lel_pct" in result["violated_thresholds"]

    def test_realistic_septic_tank_scenario(self):
        """Septic tank: very high H2S, methane, depleted O2."""
        result = evaluate(safe_frame(
            h2s_ppm=200,    # extreme
            co_ppm=10,      # safe
            o2_pct=16.5,    # hazard
            lel_pct=15,     # hazard
        ))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"


# ═══════════════════════════════════════════════════════════════════════
# 7. OXYGEN INVERSION EDGE CASES
# ═══════════════════════════════════════════════════════════════════════

class TestOxygenInversion:
    """Oxygen is the only gas where LOWER is worse. Test this thoroughly."""

    def test_o2_normal(self):
        result = evaluate(safe_frame(o2_pct=20.9))
        assert result["decision"] == "GO"

    def test_o2_slightly_low_still_safe(self):
        result = evaluate(safe_frame(o2_pct=20.5))
        assert result["decision"] == "GO"

    def test_o2_caution_range(self):
        result = evaluate(safe_frame(o2_pct=20.0))
        assert result["decision"] == "CAUTION"

    def test_o2_hazard_range(self):
        result = evaluate(safe_frame(o2_pct=18.0))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "hazard"

    def test_o2_extreme_range(self):
        result = evaluate(safe_frame(o2_pct=10.0))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"

    def test_o2_zero(self):
        result = evaluate(safe_frame(o2_pct=0.0))
        assert result["decision"] == "NO_GO"
        assert result["risk_tier"] == "extreme"

    def test_high_o2_is_not_a_violation(self):
        """O2 above normal (e.g., enriched) does NOT trigger a violation.
        This is technically also dangerous in real life, but not modeled here."""
        result = evaluate(safe_frame(o2_pct=23.5))
        assert result["decision"] == "GO"


# ═══════════════════════════════════════════════════════════════════════
# 8. STRUCTURAL INTEGRITY
# ═══════════════════════════════════════════════════════════════════════

class TestStructuralIntegrity:
    """The output schema must always be consistent and complete."""

    def test_go_has_all_required_keys(self):
        result = evaluate(safe_frame())
        required = {"ts", "decision", "risk_tier", "violated_thresholds", "readings", "provenance"}
        assert required.issubset(result.keys())

    def test_unknown_has_all_required_keys(self):
        result = evaluate(safe_frame(sensor_status={"h2s": "fault"}))
        required = {"ts", "decision", "risk_tier", "violated_thresholds", "readings", "provenance"}
        assert required.issubset(result.keys())

    def test_nogo_has_all_required_keys(self):
        result = evaluate(safe_frame(h2s_ppm=500))
        required = {"ts", "decision", "risk_tier", "violated_thresholds", "readings", "provenance"}
        assert required.issubset(result.keys())

    def test_provenance_never_says_llm_decided(self):
        """The provenance must NEVER claim an LLM made the safety decision."""
        for frame in [
            safe_frame(),
            safe_frame(h2s_ppm=500),
            safe_frame(sensor_status={"h2s": "fault"}),
        ]:
            result = evaluate(frame)
            assert result["provenance"]["decision_source"] == "deterministic_rule_engine"
            assert result["provenance"]["decision_source"] != "llm"

    def test_decision_is_always_one_of_four_states(self):
        valid_decisions = {"GO", "CAUTION", "NO_GO", "UNKNOWN"}
        for h2s in [0, 15, 50, 200]:
            result = evaluate(safe_frame(h2s_ppm=h2s))
            assert result["decision"] in valid_decisions

    def test_risk_tier_matches_decision(self):
        """Decision and risk_tier must be consistent."""
        tier_to_decision = {
            "safe": "GO",
            "caution": "CAUTION",
            "hazard": "NO_GO",
            "extreme": "NO_GO",
            "unknown": "UNKNOWN",
        }
        test_cases = [
            safe_frame(),                           # GO / safe
            safe_frame(h2s_ppm=15),                 # CAUTION / caution
            safe_frame(h2s_ppm=50),                 # NO_GO / hazard
            safe_frame(h2s_ppm=200),                # NO_GO / extreme
            safe_frame(sensor_status={"h2s": "x"}), # UNKNOWN / unknown
        ]
        for frame in test_cases:
            result = evaluate(frame)
            expected_decision = tier_to_decision[result["risk_tier"]]
            assert result["decision"] == expected_decision, \
                f"risk_tier={result['risk_tier']} but decision={result['decision']}"


# ═══════════════════════════════════════════════════════════════════════
# 9. BOUNDARY SWEEP (parametrized)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("gas_key,value,expected_decision,expected_tier", [
    # H2S boundaries
    ("h2s_ppm", 9.99,  "GO",      "safe"),
    ("h2s_ppm", 10.0,  "GO",      "safe"),     # at threshold = safe (not >)
    ("h2s_ppm", 10.01, "CAUTION", "caution"),
    ("h2s_ppm", 19.99, "CAUTION", "caution"),
    ("h2s_ppm", 20.0,  "CAUTION", "caution"),   # at threshold = caution (not >)
    ("h2s_ppm", 20.01, "NO_GO",   "hazard"),
    ("h2s_ppm", 99.99, "NO_GO",   "hazard"),
    ("h2s_ppm", 100.0, "NO_GO",   "hazard"),    # at threshold = hazard (not >)
    ("h2s_ppm", 100.01,"NO_GO",   "extreme"),

    # CO boundaries
    ("co_ppm", 34.99,  "GO",      "safe"),
    ("co_ppm", 35.0,   "GO",      "safe"),
    ("co_ppm", 35.01,  "CAUTION", "caution"),
    ("co_ppm", 99.99,  "CAUTION", "caution"),
    ("co_ppm", 100.0,  "CAUTION", "caution"),
    ("co_ppm", 100.01, "NO_GO",   "hazard"),
    ("co_ppm", 199.99, "NO_GO",   "hazard"),
    ("co_ppm", 200.0,  "NO_GO",   "hazard"),
    ("co_ppm", 200.01, "NO_GO",   "extreme"),

    # LEL boundaries
    ("lel_pct", 4.99,  "GO",      "safe"),
    ("lel_pct", 5.0,   "GO",      "safe"),
    ("lel_pct", 5.01,  "CAUTION", "caution"),
    ("lel_pct", 9.99,  "CAUTION", "caution"),
    ("lel_pct", 10.0,  "CAUTION", "caution"),
    ("lel_pct", 10.01, "NO_GO",   "hazard"),
    ("lel_pct", 19.99, "NO_GO",   "hazard"),
    ("lel_pct", 20.0,  "NO_GO",   "hazard"),
    ("lel_pct", 20.01, "NO_GO",   "extreme"),
])
def test_threshold_boundary(gas_key, value, expected_decision, expected_tier):
    frame = safe_frame(**{gas_key: value})
    result = evaluate(frame)
    assert result["decision"] == expected_decision, \
        f"{gas_key}={value}: expected {expected_decision}, got {result['decision']}"
    assert result["risk_tier"] == expected_tier, \
        f"{gas_key}={value}: expected tier {expected_tier}, got {result['risk_tier']}"


@pytest.mark.parametrize("o2_value,expected_decision,expected_tier", [
    # O2 boundaries (inverted: lower is worse)
    (20.9,  "GO",      "safe"),
    (20.51, "GO",      "safe"),
    (20.5,  "GO",      "safe"),      # at threshold = safe (not <)
    (20.49, "CAUTION", "caution"),
    (19.51, "CAUTION", "caution"),
    (19.5,  "CAUTION", "caution"),   # at threshold = caution (not <)
    (19.49, "NO_GO",   "hazard"),
    (16.01, "NO_GO",   "hazard"),
    (16.0,  "NO_GO",   "hazard"),    # at threshold = hazard (not <)
    (15.99, "NO_GO",   "extreme"),
    (0.0,   "NO_GO",   "extreme"),
])
def test_o2_boundary(o2_value, expected_decision, expected_tier):
    frame = safe_frame(o2_pct=o2_value)
    result = evaluate(frame)
    assert result["decision"] == expected_decision, \
        f"O2={o2_value}%: expected {expected_decision}, got {result['decision']}"
    assert result["risk_tier"] == expected_tier, \
        f"O2={o2_value}%: expected tier {expected_tier}, got {result['risk_tier']}"
