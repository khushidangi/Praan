"""Load and validate safety limits configuration."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class GasLimits:
    """Limits for a single gas."""
    lower: Optional[float] = None
    upper: Optional[float] = None
    unit: str = ""
    source: str = ""
    
    @property
    def has_citation(self) -> bool:
        """Check if source citation exists and is not a placeholder."""
        return bool(self.source and not self.source.startswith("TODO"))


@dataclass
class SafetyConfig:
    """Complete safety configuration loaded from limits.yaml."""
    authority: str
    freshness_seconds: int
    stabilization_seconds: int
    recovery_consecutive_readings: int
    warn_margin_fraction: float
    predict_horizon_seconds: int
    go_valid_minutes: int
    gases: Dict[str, GasLimits]
    physical_range: Dict[str, tuple]
    
    @property
    def all_citations_valid(self) -> bool:
        """Check if all gas limits have valid citations."""
        if not self.authority or self.authority.startswith("TODO"):
            return False
        return all(gas.has_citation for gas in self.gases.values())
    
    @property
    def missing_citations(self) -> list:
        """Return list of gases missing valid citations."""
        missing = []
        if not self.authority or self.authority.startswith("TODO"):
            missing.append("authority")
        for gas_key, limits in self.gases.items():
            if not limits.has_citation:
                missing.append(gas_key)
        return missing


def load_config(config_path: Optional[Path] = None) -> SafetyConfig:
    """Load safety configuration from YAML file.
    
    Args:
        config_path: Path to limits.yaml. If None, uses default location.
        
    Returns:
        SafetyConfig object with loaded configuration.
        
    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is malformed.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "limits.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Safety limits config not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Parse gas limits
    gases = {}
    for gas_key, gas_data in data.get("gases", {}).items():
        gases[gas_key] = GasLimits(
            lower=gas_data.get("lower"),
            upper=gas_data.get("upper"),
            unit=gas_data.get("unit", ""),
            source=gas_data.get("source", "")
        )
    
    # Parse physical ranges
    physical_range = {}
    for gas_key, range_list in data.get("physical_range", {}).items():
        if len(range_list) == 2:
            physical_range[gas_key] = tuple(range_list)
    
    return SafetyConfig(
        authority=data.get("authority", ""),
        freshness_seconds=data.get("freshness_seconds", 6),
        stabilization_seconds=data.get("stabilization_seconds", 60),
        recovery_consecutive_readings=data.get("recovery_consecutive_readings", 5),
        warn_margin_fraction=data.get("warn_margin_fraction", 0.20),
        predict_horizon_seconds=data.get("predict_horizon_seconds", 120),
        go_valid_minutes=data.get("go_valid_minutes", 30),
        gases=gases,
        physical_range=physical_range
    )


# Global config instance (loaded once at import)
_config: Optional[SafetyConfig] = None


def get_config() -> SafetyConfig:
    """Get the global safety configuration (singleton)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
