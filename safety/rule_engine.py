# safety/rule_engine.py — deterministic GO/NO-GO logic
#
# This is the most important file in the entire repository.
# It is pure Python, no models, no ML, no network calls.
# A judge should be able to read it top to bottom and verify by hand.
#
# Decision states:
#   GO      — all readings within safe limits, all sensors operational
#   CAUTION — one or more readings approaching a threshold; re-test
#   NO_GO   — a defined hazardous condition exists; do not enter
#   UNKNOWN — sensor fault or missing data; atmosphere cannot be verified
#
# The LLM never touches this file's output. It only explains it afterward.

from safety.thresholds import THRESHOLDS, EXPECTED_SENSORS

# Tier severity ordering (index = severity, higher = worse)
_SEVERITY = ["caution", "hazard", "extreme"]


def evaluate(frame: dict) -> dict:
    """Evaluate a probe telemetry frame and return a safety decision.

    Args:
        frame: A dict matching the §3.1 probe telemetry schema:
            {
                "ts": <unix timestamp>,
                "h2s_ppm": <float>,
                "co_ppm": <float>,
                "o2_pct": <float>,
                "lel_pct": <float>,
                "sensor_status": {"h2s": "ok"|..., "co": ..., "o2": ..., "lel": ...},
                "probe_depth_m": <float>
            }

    Returns:
        A dict matching the §3.2 rule-engine decision schema.
    """
    sensor_status = frame.get("sensor_status", {})
    sensors_reporting = set(sensor_status.keys())
    sensors_ok = sum(1 for s in sensor_status.values() if s == "ok")
    total_expected = len(EXPECTED_SENSORS)

    provenance = {
        "decision_source": "deterministic_rule_engine",
        "explanation_source": "on_device_llm",
        "sensors_operational": f"{sensors_ok}/{total_expected}",
        "reading_age_sec": 0,  # Will be updated by the pipeline with actual age
    }

    # ── UNKNOWN: any sensor not reporting "ok" ──────────────────────────
    # This is a DISTINCT state from NO_GO.
    # It means "we cannot verify the atmosphere," NOT "we verified and it's dangerous."
    # It must never render identically to a stable GO in the UI.
    missing_sensors = EXPECTED_SENSORS - sensors_reporting
    faulty_sensors = [k for k, v in sensor_status.items() if v != "ok"]

    if missing_sensors or faulty_sensors:
        fault_details = []
        if missing_sensors:
            fault_details.extend(f"{s}_missing" for s in sorted(missing_sensors))
        if faulty_sensors:
            fault_details.extend(f"{s}_fault" for s in sorted(faulty_sensors))

        return {
            "ts": frame.get("ts", 0),
            "decision": "UNKNOWN",
            "risk_tier": "unknown",
            "violated_thresholds": fault_details,
            "readings": frame,
            "provenance": provenance,
        }

    # ── Threshold evaluation ────────────────────────────────────────────
    violations = []

    for gas_key, limits in THRESHOLDS.items():
        value = frame.get(gas_key)

        if value is None:
            # Missing reading for a gas we expect — treat as sensor fault
            return {
                "ts": frame.get("ts", 0),
                "decision": "UNKNOWN",
                "risk_tier": "unknown",
                "violated_thresholds": [f"{gas_key}_missing_reading"],
                "readings": frame,
                "provenance": provenance,
            }

        if gas_key == "o2_pct":
            # Oxygen is INVERTED: LOWER is worse
            if value < limits["extreme"]:
                violations.append((gas_key, "extreme", value))
            elif value < limits["hazard"]:
                violations.append((gas_key, "hazard", value))
            elif value < limits["caution"]:
                violations.append((gas_key, "caution", value))
        else:
            # All other gases: HIGHER is worse
            if value > limits["extreme"]:
                violations.append((gas_key, "extreme", value))
            elif value > limits["hazard"]:
                violations.append((gas_key, "hazard", value))
            elif value > limits["caution"]:
                violations.append((gas_key, "caution", value))

    # ── No violations → GO ──────────────────────────────────────────────
    if not violations:
        return {
            "ts": frame.get("ts", 0),
            "decision": "GO",
            "risk_tier": "safe",
            "violated_thresholds": [],
            "readings": frame,
            "provenance": provenance,
        }

    # ── Find worst violation ────────────────────────────────────────────
    worst = max(violations, key=lambda v: _SEVERITY.index(v[1]))

    # CAUTION is its own decision state, not silently folded into GO.
    # A supervisor should be told to re-test, not given a clean green light.
    decision_map = {
        "caution": "CAUTION",
        "hazard": "NO_GO",
        "extreme": "NO_GO",
    }

    return {
        "ts": frame.get("ts", 0),
        "decision": decision_map[worst[1]],
        "risk_tier": worst[1],
        "violated_thresholds": [v[0] for v in violations],
        "readings": frame,
        "provenance": provenance,
    }
