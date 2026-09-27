# Praan: Pre-Entry Safety Intelligence for Confined Space Sanitation Work

*Praan (प्राण) means breath, or life-force: the thing this device exists to protect before someone climbs into a space where the air itself can kill them.*

---

## What This Is

Praan is a safety system that checks whether it's safe to enter sewers, septic tanks, and other confined spaces before any human goes in. It uses a gas probe, deterministic safety rules, and on-device AI to give supervisors a clear GO/NO-GO decision with spoken guidance in local languages — entirely offline.

**The AI never decides whether it's safe.** A deterministic rule engine makes that call. The AI only explains the decision in plain language.

## Current Implementation Status

### ✅ Completed Components
- **Safety Rule Engine**: Deterministic GO/CAUTION/NO-GO/UNKNOWN decisions based on OSHA/NIOSH thresholds
- **Comprehensive Unit Tests**: Full boundary testing for all decision states
- **Simulated Probe**: Realistic gas sensor simulation with multiple scenarios
- **FastAPI Backend**: WebSocket telemetry, REST API, offline-first SQLite storage
- **Field Unit Dashboard**: Real-time sensor display, decision banner, guidance panel, provenance tracking
- **City Layer Dashboard**: Site management, inspection history, hazard mapping
- **Guidance Pipeline**: Template-based local-language guidance (Hindi + English)
- **Voice Pipeline**: Placeholder TTS infrastructure (ready for MMS-TTS integration)

### ⚠️ Pending Components (Hardware/Model Integration)
- **Arduino Probe Firmware**: Hardware not yet available (using simulated probe)
- **Genie LLM Integration**: Requires Qualcomm Genie SDK and compiled model
- **Meta MMS-TTS Model**: Requires ONNX model download
- **Predictive Risk Model**: Requires training data (currently using rule-based only)

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd praan

# Install dependencies
pip install -r requirements.txt

# Run tests
python run.py test

# Start the backend server
python run.py backend
```

Then open:
- **Field Unit Dashboard**: http://localhost:8000/dashboard
- **City Layer Dashboard**: http://localhost:8000/city
- **API Documentation**: http://localhost:8000/docs

### Demo Scenarios

The simulated probe supports multiple scenarios for demonstration:

```bash
# Run standalone simulated probe
python run.py probe --scenario safe
python run.py probe --scenario h2s_buildup
python run.py probe --scenario o2_depletion
python run.py probe --scenario sensor_fault
python run.py probe --scenario mixed_hazard
```

Or use the demo controls in the Field Unit Dashboard to switch scenarios live.

## Architecture

### Three Tiers

1. **Probe** (Arduino + 4 gas sensors): Measures H₂S, CO, O₂, and combustible gas (LEL)
2. **Field Unit** (Snapdragon PC): Runs rule engine, LLM guidance, TTS, dashboard
3. **City Layer** (Municipal office): Aggregates inspections across sites

### Data Flow

```
Probe → Rule Engine → Decision → LLM Explanation → TTS → Dashboard
                                                    ↓
                                              SQLite (offline)
                                                    ↓
                                              City Layer (when online)
```

### The Four Decision States

- **GO**: All readings safe, entry permitted
- **CAUTION**: Approaching threshold, re-test before proceeding
- **NO-GO**: Hazardous conditions detected, do not enter
- **UNKNOWN**: Sensor fault, atmosphere cannot be verified

**Critical**: UNKNOWN is distinct from NO-GO. It means "we can't verify" not "we verified and it's dangerous." It must never look like a safe reading in the UI.

## Safety Thresholds

Based on OSHA/NIOSH standards:

| Gas | Caution | Hazard | Extreme | Reference |
|-----|---------|--------|---------|-----------|
| H₂S | 10 ppm | 20 ppm | 100 ppm | OSHA PEL / NIOSH IDLH |
| CO | 35 ppm | 100 ppm | 200 ppm | OSHA PEL |
| O₂ | <20.5% | <19.5% | <16% | OSHA confined space std |
| LEL | 5% | 10% | 20% | OSHA action level |

See `safety/thresholds.py` for full citations.

## Development

### Project Structure

```
praan/
├── safety/              # Rule engine (MOST IMPORTANT CODE)
│   ├── thresholds.py    # OSHA/NIOSH reference thresholds
│   └── rule_engine.py   # Deterministic decision logic
├── backend/
│   ├── app.py           # FastAPI application
│   ├── state_store.py   # SQLite persistence
│   └── simulated_probe.py
├── pipeline/
│   ├── guidance.py      # LLM guidance generation
│   └── voice.py         # TTS synthesis
├── dashboard/           # HTML dashboards
├── firmware/            # Arduino probe firmware (pending hardware)
├── tests/
│   └── unit/
│       └── test_rule_engine.py  # Most important tests
├── docs/                # Project documentation
├── requirements.txt
├── run.py               # Launch script
└── README.md
```

### Running Tests

```bash
# Run all tests
python run.py test

# Run specific test file
pytest tests/unit/test_rule_engine.py -v

# Run with coverage
pytest --cov=safety --cov=backend --cov=pipeline tests/
```

### API Endpoints

- `GET /` - Landing page
- `GET /dashboard` - Field unit dashboard
- `GET /city` - City layer dashboard
- `WS /ws/telemetry` - Live telemetry stream
- `POST /api/inspection` - Record inspection
- `GET /api/sites` - List monitored sites
- `GET /api/sites/{id}/history` - Site inspection history
- `POST /api/simulate/scenario` - Change demo scenario

## Hardware Integration (When Available)

### Probe Hardware Requirements

- Arduino UNO or compatible board
- Gas sensors:
  - H₂S electrochemical sensor
  - CO electrochemical sensor
  - O₂ sensor
  - LEL/methane sensor
- LED + buzzer for dead-man's-switch alert
- Weatherproof housing
- 5-8m tether cable

### Connecting Real Hardware

Replace simulated probe in `backend/app.py`:

```python
# Instead of:
from backend.simulated_probe import SimulatedProbe
simulated_probe = SimulatedProbe()

# Use:
import serial
probe_serial = serial.Serial('/dev/ttyUSB0', 115200)

# In WebSocket handler:
frame = json.loads(probe_serial.readline())
```

## AI Model Integration (When Available)

### Genie LLM Setup

```bash
# Install AI Hub tools
pip install "qai_hub_models[llama-v3-2-3b-chat-quantized]"

# Compile model
python -m qai_hub_models.models.llama_v3_2_3b_chat_quantized.export \
  --device "Snapdragon X Elite CRD" \
  --skip-inferencing --skip-profiling \
  --output-dir models/genie_bundle

# Enable in guidance.py:
generator = GuidanceGenerator(
    genie_bundle_path=Path("models/genie_bundle"),
    use_genie=True
)
```

### Meta MMS-TTS Setup

1. Download ONNX model from [MMS-TTS repository]
2. Place in `models/tts/`
3. Update `voice.py` to load the model

## Licensing

### Project Code
[Your chosen open-source license]

### TTS Model (Meta MMS-TTS)
**CC-BY-NC-4.0 (Non-commercial use only)**

This is acceptable for a hackathon prototype but must be replaced with a commercially-licensed TTS model for production deployment to government agencies.

## Limitations & Path to Certification

**This is a decision-support prototype, not a certified life-safety instrument.**

Certified confined-space gas detectors (Dräger, MSA, BW Technologies) undergo calibration and regulatory validation that this project has not completed. The realistic next step is:

1. **Pilot with one ULB** (Urban Local Body) using simulated or training scenarios
2. **Cross-validate** readings against certified reference meters
3. **Field testing** with ERSU teams in controlled conditions
4. **Certification path** through relevant Indian standards (BIS)

## Government Collaboration

### Target Program
**NAMASTE Scheme** (National Action for Mechanised Sanitation Ecosystem)
- Joint program: Ministry of Social Justice & Empowerment + Ministry of Housing & Urban Affairs
- Operational since 2023-24
- Funds PPE, mechanized equipment, and ERSU safety devices

### Realistic Next Steps
1. Demo to NSKFDC (implementing agency)
2. Pilot with willing ULB's ERSU team
3. Use pilot data for inclusion in NAMASTE equipment list

## Contributing

Contributions welcome! Priority areas:
- Arduino firmware implementation
- Genie LLM integration
- MMS-TTS integration
- Additional language support
- Field testing feedback

## Acknowledgments

- Built for Qualcomm Snapdragon Challenge
- Safety thresholds from OSHA/NIOSH standards
- Designed for NAMASTE scheme deployment

## Contact

[Your contact information]

---

*This project addresses a documented, ongoing cause of death in sanitation work. At least 453 deaths have been recorded since 2014 during sewer and septic tank cleaning, almost all from toxic or oxygen-deficient atmospheres. This system exists to help prevent those deaths.*
