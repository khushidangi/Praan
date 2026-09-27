"""Simulated probe for development without Arduino hardware.

Generates realistic telemetry frames with configurable scenarios:
- Safe conditions
- Gradual H2S buildup (sewer scenario)
- Oxygen depletion (septic tank scenario)
- Sensor faults
- Mixed hazards
"""

import time
import random
import json
from typing import Dict, Literal

ScenarioType = Literal["safe", "h2s_buildup", "o2_depletion", "sensor_fault", "mixed_hazard"]


class SimulatedProbe:
    """Simulates a 4-sensor gas probe with realistic behavior."""

    def __init__(self, scenario: ScenarioType = "safe", seed: int = None):
        self.scenario = scenario
        self.start_time = time.time()
        self.random = random.Random(seed)
        self._sensor_status = {"h2s": "ok", "co": "ok", "o2": "ok", "lel": "ok"}

    def read_frame(self) -> Dict:
        """Generate a single telemetry frame based on current scenario."""
        elapsed = time.time() - self.start_time

        frame = {
            "ts": time.time(),
            "h2s_ppm": 0.0,
            "co_ppm": 0.0,
            "o2_pct": 20.9,
            "lel_pct": 0.0,
            "sensor_status": self._sensor_status.copy(),
            "probe_depth_m": 4.2,
        }

        # Add realistic noise
        noise_scale = 0.05

        if self.scenario == "safe":
            frame["h2s_ppm"] = max(0, self.random.gauss(1.0, noise_scale))
            frame["co_ppm"] = max(0, self.random.gauss(5.0, noise_scale * 5))
            frame["o2_pct"] = self.random.gauss(20.9, noise_scale * 0.2)
            frame["lel_pct"] = max(0, self.random.gauss(0.5, noise_scale))

        elif self.scenario == "h2s_buildup":
            # Simulate gradual H2S increase over 60 seconds
            progress = min(1.0, elapsed / 60.0)
            frame["h2s_ppm"] = progress * 150 + self.random.gauss(0, 2)
            frame["co_ppm"] = max(0, self.random.gauss(8.0, 1))
            frame["o2_pct"] = 20.9 - progress * 2.0 + self.random.gauss(0, 0.1)
            frame["lel_pct"] = progress * 8 + self.random.gauss(0, 0.5)

        elif self.scenario == "o2_depletion":
            # Simulate oxygen depletion (septic tank scenario)
            progress = min(1.0, elapsed / 45.0)
            frame["h2s_ppm"] = 30 + progress * 50 + self.random.gauss(0, 3)
            frame["co_ppm"] = max(0, self.random.gauss(15.0, 2))
            frame["o2_pct"] = 20.9 - progress * 8.0 + self.random.gauss(0, 0.2)
            frame["lel_pct"] = 12 + progress * 10 + self.random.gauss(0, 1)

        elif self.scenario == "sensor_fault":
            # Simulate sensor fault after 10 seconds
            if elapsed > 10:
                self._sensor_status["h2s"] = "fault"
                frame["sensor_status"]["h2s"] = "fault"
            frame["h2s_ppm"] = max(0, self.random.gauss(5.0, 1))
            frame["co_ppm"] = max(0, self.random.gauss(5.0, 1))
            frame["o2_pct"] = self.random.gauss(20.9, 0.1)
            frame["lel_pct"] = max(0, self.random.gauss(1.0, 0.2))

        elif self.scenario == "mixed_hazard":
            # Realistic sewer scenario: high H2S + low O2 + some methane
            frame["h2s_ppm"] = 45 + self.random.gauss(0, 5)
            frame["co_ppm"] = max(0, self.random.gauss(5.0, 1))
            frame["o2_pct"] = 19.0 + self.random.gauss(0, 0.2)
            frame["lel_pct"] = 8 + self.random.gauss(0, 1)

        # Clamp values to realistic ranges
        frame["h2s_ppm"] = max(0, frame["h2s_ppm"])
        frame["co_ppm"] = max(0, frame["co_ppm"])
        frame["o2_pct"] = max(0, min(100, frame["o2_pct"]))
        frame["lel_pct"] = max(0, min(100, frame["lel_pct"]))

        return frame

    def set_scenario(self, scenario: ScenarioType):
        """Change the simulation scenario on the fly."""
        self.scenario = scenario
        self.start_time = time.time()
        # Reset sensor status
        self._sensor_status = {"h2s": "ok", "co": "ok", "o2": "ok", "lel": "ok"}


# ──────────────────────────────────────────────────────────────────────
# CLI interface for testing
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Simulated gas probe")
    parser.add_argument(
        "--scenario",
        choices=["safe", "h2s_buildup", "o2_depletion", "sensor_fault", "mixed_hazard"],
        default="safe",
        help="Simulation scenario",
    )
    parser.add_argument(
        "--interval", type=float, default=2.0, help="Polling interval in seconds"
    )

    args = parser.parse_args()

    probe = SimulatedProbe(scenario=args.scenario)

    print(f"Simulated probe started (scenario: {args.scenario})", file=sys.stderr)
    print(f"Emitting telemetry every {args.interval}s", file=sys.stderr)
    print("─" * 60, file=sys.stderr)

    try:
        while True:
            frame = probe.read_frame()
            print(json.dumps(frame))
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
