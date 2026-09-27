# safety/thresholds.py — cite your source for every number
#
# These are the single source of truth for GO/CAUTION/NO-GO/UNKNOWN decisions.
# Every threshold here comes from a published occupational exposure standard.
# Do NOT modify these without updating the citation.
#
# References:
#   - NIOSH IDLH (Immediately Dangerous to Life or Health):
#     https://www.cdc.gov/niosh/idlh/
#   - OSHA PEL (Permissible Exposure Limits):
#     https://www.osha.gov/annotated-pels
#   - OSHA Confined Space Standard (29 CFR 1910.146)
#
# Threshold tiers:
#   caution  — approaching danger; re-test, alert supervisor
#   hazard   — confirmed hazardous; NO-GO
#   extreme  — immediately dangerous to life; NO-GO, evacuate area

THRESHOLDS = {
    # H2S: NIOSH IDLH = 50 ppm (revised), OSHA ceiling = 20 ppm,
    # OSHA PEL (general industry) = 20 ppm ceiling.
    # Using conservative stepped tiers below IDLH.
    "h2s_ppm": {
        "caution": 10,    # Noticeable odor, beginning of irritation
        "hazard": 20,     # OSHA ceiling / PEL
        "extreme": 100,   # Well above IDLH — immediately life-threatening
    },

    # CO: NIOSH IDLH = 1200 ppm, OSHA PEL = 50 ppm (8-hr TWA).
    # Using conservative stepped tiers.
    "co_ppm": {
        "caution": 35,    # OSHA short-term action level
        "hazard": 100,    # Headache, dizziness within 1–2 hours
        "extreme": 200,   # Dangerous with short exposure
    },

    # O2: Normal atmospheric = 20.9%.
    # OSHA defines oxygen-deficient atmosphere as < 19.5%.
    # NOTE: For O2, LOWER values are MORE dangerous (inverted logic).
    "o2_pct": {
        "caution": 20.5,  # Slightly below normal — investigate
        "hazard": 19.5,   # OSHA oxygen-deficient threshold
        "extreme": 16.0,  # Impaired judgment, rapid incapacitation risk
    },

    # LEL: Percentage of Lower Explosive Limit.
    # OSHA action level for confined space = 10% LEL.
    # Most instruments alarm at 10% LEL; 20%+ is immediate explosion risk.
    "lel_pct": {
        "caution": 5,     # Combustible gas detected — investigate source
        "hazard": 10,     # OSHA action level
        "extreme": 20,    # Immediate explosion risk
    },
}

# Gas names for human-readable output
GAS_NAMES = {
    "h2s_ppm": "Hydrogen Sulfide (H₂S)",
    "co_ppm": "Carbon Monoxide (CO)",
    "o2_pct": "Oxygen (O₂)",
    "lel_pct": "Combustible Gas (LEL)",
}

# Units for display
GAS_UNITS = {
    "h2s_ppm": "ppm",
    "co_ppm": "ppm",
    "o2_pct": "%",
    "lel_pct": "% LEL",
}

# The four sensor keys the system expects
EXPECTED_SENSORS = frozenset(["h2s", "co", "o2", "lel"])
