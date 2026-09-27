# safety/__init__.py
"""Safety layer — deterministic, auditable, first."""

from safety.rule_engine import evaluate
from safety.thresholds import THRESHOLDS, GAS_NAMES, GAS_UNITS, EXPECTED_SENSORS

__all__ = ["evaluate", "THRESHOLDS", "GAS_NAMES", "GAS_UNITS", "EXPECTED_SENSORS"]
