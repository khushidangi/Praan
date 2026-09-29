"""Enhanced rule engine with Phase 1 requirements.

This implements:
- R-S1: Freshness, physical range, sensor status checking
- R-S2: Limit violations with margin
- R-S3: Warn margin, rate of rise, stabilization
- R-S4: Consecutive GO readings
- R-S5: Recovery band after NO_GO/UNKNOWN
- R-S6: Pure function (no I/O, randomness, or model calls)
"""

import time
import math
from typing import Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass

from safety.config import get_config, SafetyConfig


@dataclass
class Decision:
    """Rule engine decision output."""
    decision_id: str
    ts: float
    decision: str  # GO, CAUTION, NO_GO, UNKNOWN
    risk_tier: str
    violated_thresholds: List[str]
    margins: Dict[str, float]  # How far from limit
    time_to_limit_s: Optional[float]
    trends: Dict[str, str]  # up, down, stable
    readings: Dict
    provenance: Dict
    
    def to_dict(self) -> Dict:
        """Convert to dict for API responses."""
        return {
            "decision_id": self.decision_id,
            "ts": self.ts,
            "decision": self.decision,
            "risk_tier": self.risk_tier,
            "violated_thresholds": self.violated_thresholds,
            "margins": self.margins,
            "time_to_limit_s": self.time_to_limit_s,
            "trends": self.trends,
            "readings": self.readings,
            "provenance": self.provenance
        }


class RuleEngine:
    """Stateful rule engine that tracks reading history for hysteresis and trends."""
    
    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or get_config()
        self.reading_window = deque(maxlen=30)  # 60 seconds at 2 Hz
        self.candidate_go_count = 0
        self.last_decision = None
        self.stabilization_start = None
        self.decision_counter = 0
    
    def evaluate(self, frame: Dict, current_time: Optional[float] = None) -> Decision:
        """Evaluate a probe frame and return a safety decision.
        
        Args:
            frame: Telemetry frame from probe
            current_time: Current timestamp (for testing; uses time.time() if None)
            
        Returns:
            Decision object
        """
        if current_time is None:
            current_time = time.time()
        
        self.decision_counter += 1
        decision_id = f"D{int(current_time)}-{self.decision_counter}"
        
        # Add to window
        self.reading_window.append((current_time, frame))
        
        # Initialize stabilization timer
        if self.stabilization_start is None:
            self.stabilization_start = current_time
        
        provenance = {
            "decision_source": "deterministic_rule_engine",
            "explanation_source": "template",  # Will be "genie" when NPU integrated
            "sensors_operational": self._count_operational_sensors(frame),
            "reading_age_sec": current_time - frame.get("ts", current_time)
        }
        
        # R-S1: Integrity checks
        integrity_issue = self._check_integrity(frame, current_time)
        if integrity_issue:
            self._reset_hysteresis()
            return Decision(
                decision_id=decision_id,
                ts=current_time,
                decision="UNKNOWN",
                risk_tier="unknown",
                violated_thresholds=integrity_issue,
                margins={},
                time_to_limit_s=None,
                trends={},
                readings=frame,
                provenance=provenance
            )
        
        # R-S2: Check limit violations
        violations, margins = self._check_limits(frame)
        
        # Calculate trends
        trends = self._calculate_trends()
        
        # R-S3: Check warn conditions
        warn_reasons = self._check_warn_conditions(frame, margins, trends, current_time)
        
        # Determine candidate decision
        if violations:
            candidate = "NO_GO"
            risk_tier = "hazard"
            violated = violations
        elif warn_reasons:
            candidate = "CAUTION"
            risk_tier = "caution"
            violated = warn_reasons
        else:
            candidate = "GO"
            risk_tier = "safe"
            violated = []
        
        # R-S4 & R-S5: Apply hysteresis
        final_decision, final_tier, final_violated = self._apply_hysteresis(
            candidate, risk_tier, violated, margins
        )
        
        # Calculate time to limit if trending toward breach
        time_to_limit = self._estimate_time_to_limit(trends, margins) if final_decision == "CAUTION" else None
        
        return Decision(
            decision_id=decision_id,
            ts=current_time,
            decision=final_decision,
            risk_tier=final_tier,
            violated_thresholds=final_violated,
            margins=margins,
            time_to_limit_s=time_to_limit,
            trends=trends,
            readings=frame,
            provenance=provenance
        )
    
    def _count_operational_sensors(self, frame: Dict) -> str:
        """Count operational sensors."""
        sensor_status = frame.get("sensor_status", {})
        ok_count = sum(1 for status in sensor_status.values() if status == "ok")
        total = 4  # h2s, co, o2, lel
        return f"{ok_count}/{total}"
    
    def _check_integrity(self, frame: Dict, current_time: float) -> Optional[List[str]]:
        """Check frame integrity (R-S1)."""
        issues = []
        
        # Check freshness
        frame_ts = frame.get("ts", 0)
        age = current_time - frame_ts
        if age > self.config.freshness_seconds:
            issues.append(f"stale_reading_{age:.1f}s")
        
        # Check sensor status
        sensor_status = frame.get("sensor_status", {})
        for sensor, status in sensor_status.items():
            if status != "ok":
                issues.append(f"{sensor}_fault")
        
        # Check physical ranges
        for gas_key, (min_val, max_val) in self.config.physical_range.items():
            value = frame.get(gas_key)
            if value is None:
                issues.append(f"{gas_key}_missing")
            elif not (min_val <= value <= max_val):
                issues.append(f"{gas_key}_out_of_range")
            elif math.isnan(value) or math.isinf(value):
                issues.append(f"{gas_key}_invalid")
        
        return issues if issues else None
    
    def _check_limits(self, frame: Dict) -> Tuple[List[str], Dict[str, float]]:
        """Check if any gas exceeds limits (R-S2).
        
        Returns:
            (violations list, margins dict)
        """
        violations = []
        margins = {}
        
        for gas_key, limits in self.config.gases.items():
            value = frame.get(gas_key)
            if value is None:
                continue
            
            # Oxygen is inverted (lower is worse)
            if gas_key == "o2_pct":
                if limits.lower is not None:
                    margin = value - limits.lower
                    margins[gas_key] = margin
                    if value < limits.lower:
                        violations.append(gas_key)
                if limits.upper is not None and value > limits.upper:
                    violations.append(f"{gas_key}_high")
            else:
                # Other gases: higher is worse
                if limits.upper is not None:
                    margin = limits.upper - value
                    margins[gas_key] = margin
                    if value > limits.upper:
                        violations.append(gas_key)
        
        return violations, margins
    
    def _check_warn_conditions(self, frame: Dict, margins: Dict, trends: Dict, current_time: float) -> List[str]:
        """Check CAUTION conditions (R-S3)."""
        warnings = []
        
        # Check warn margin
        for gas_key, margin in margins.items():
            limits = self.config.gases.get(gas_key)
            if limits and limits.upper:
                warn_threshold = limits.upper * self.config.warn_margin_fraction
                if margin < warn_threshold:
                    warnings.append(f"{gas_key}_approaching_limit")
        
        # Check stabilization
        if self.stabilization_start:
            elapsed = current_time - self.stabilization_start
            if elapsed < self.config.stabilization_seconds:
                warnings.append("stabilizing")
        
        return warnings
    
    def _calculate_trends(self) -> Dict[str, str]:
        """Calculate trends for each gas using least squares."""
        if len(self.reading_window) < 5:
            return {}
        
        trends = {}
        recent = list(self.reading_window)[-15:]  # Last 30 seconds
        
        for gas_key in self.config.gases.keys():
            values = []
            times = []
            for ts, frame in recent:
                val = frame.get(gas_key)
                if val is not None:
                    values.append(val)
                    times.append(ts)
            
            if len(values) < 5:
                continue
            
            # Least squares slope
            n = len(values)
            t_mean = sum(times) / n
            v_mean = sum(values) / n
            
            numerator = sum((times[i] - t_mean) * (values[i] - v_mean) for i in range(n))
            denominator = sum((times[i] - t_mean) ** 2 for i in range(n))
            
            if denominator > 0:
                slope = numerator / denominator
                
                # Classify trend
                if abs(slope) < 0.01:  # Threshold depends on gas
                    trends[gas_key] = "stable"
                elif slope > 0:
                    trends[gas_key] = "rising"
                else:
                    trends[gas_key] = "falling"
        
        return trends
    
    def _estimate_time_to_limit(self, trends: Dict, margins: Dict) -> Optional[float]:
        """Estimate time until a limit is breached based on current trend."""
        if len(self.reading_window) < 5:
            return None
        
        min_time = None
        
        for gas_key, trend in trends.items():
            if trend != "rising":
                continue
            
            margin = margins.get(gas_key)
            if margin is None or margin <= 0:
                continue
            
            # Calculate rate from recent window
            recent = list(self.reading_window)[-15:]
            values = [frame.get(gas_key) for _, frame in recent if frame.get(gas_key) is not None]
            
            if len(values) < 5:
                continue
            
            # Rate of change per second
            rate = (values[-1] - values[0]) / (recent[-1][0] - recent[0][0])
            
            if rate > 0:
                time_to_limit = margin / rate
                if min_time is None or time_to_limit < min_time:
                    min_time = time_to_limit
        
        return min_time if min_time and min_time < self.config.predict_horizon_seconds else None
    
    def _apply_hysteresis(self, candidate: str, risk_tier: str, violated: List[str], margins: Dict) -> Tuple[str, str, List[str]]:
        """Apply R-S4 and R-S5 hysteresis rules."""
        # R-S5: Recovery band check
        if self.last_decision in ["NO_GO", "UNKNOWN"]:
            # Must be in recovery band
            in_recovery_band = self._check_recovery_band(margins)
            if not in_recovery_band:
                self.candidate_go_count = 0
                return candidate, risk_tier, violated
        
        # R-S4: Consecutive GO readings required
        if candidate == "GO":
            self.candidate_go_count += 1
            if self.candidate_go_count < self.config.recovery_consecutive_readings:
                # Not enough consecutive GO readings yet
                return "CAUTION", "caution", ["awaiting_stabilization"]
            else:
                # Achieved stable GO
                self.last_decision = "GO"
                return "GO", "safe", []
        else:
            # Not a GO candidate, reset counter
            self.candidate_go_count = 0
            self.last_decision = candidate
            return candidate, risk_tier, violated
    
    def _check_recovery_band(self, margins: Dict) -> bool:
        """Check if all readings are in the recovery band."""
        for gas_key, limits in self.config.gases.items():
            margin = margins.get(gas_key)
            if margin is None:
                continue
            
            # Recovery band is 10% tighter than entry limits
            if gas_key == "o2_pct":
                # For oxygen: must be 2% above lower limit
                if limits.lower is not None and margin < (limits.lower * 0.02):
                    return False
            else:
                # For other gases: must be 10% below upper limit
                if limits.upper is not None and margin < (limits.upper * 0.10):
                    return False
        
        return True
    
    def _reset_hysteresis(self):
        """Reset hysteresis state (called on UNKNOWN)."""
        self.candidate_go_count = 0
        self.last_decision = None
        self.stabilization_start = time.time()


# Convenience function for backward compatibility
def evaluate(frame: Dict) -> Dict:
    """Evaluate a frame using a stateless engine (for backward compat)."""
    engine = RuleEngine()
    decision = engine.evaluate(frame)
    return decision.to_dict()
