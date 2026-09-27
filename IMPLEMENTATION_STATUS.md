# Praan Implementation Status

**Last Updated**: January 2025

## ✅ Completed Components

### Core Safety System
- [x] **Rule Engine** (`safety/rule_engine.py`)
  - Deterministic GO/CAUTION/NO-GO/UNKNOWN decision logic
  - Based on OSHA/NIOSH occupational exposure thresholds
  - Four-state decision model (not binary safe/unsafe)
  - Sensor fault detection and UNKNOWN state handling
  - Complete provenance tracking (decision source vs explanation source)
  
- [x] **Safety Thresholds** (`safety/thresholds.py`)
  - Cited reference thresholds for H₂S, CO, O₂, LEL
  - Three-tier severity: caution / hazard / extreme
  - Oxygen inversion logic (lower is worse)
  - Single source of truth for all safety decisions

- [x] **Comprehensive Unit Tests** (`tests/unit/test_rule_engine.py`)
  - 90 passing tests covering all boundary conditions
  - All decision states tested
  - Sensor fault combinations
  - Multi-gas scenarios
  - Provenance verification

### Simulated Probe
- [x] **Simulated Probe** (`backend/simulated_probe.py`)
  - Realistic 4-sensor gas probe simulation
  - 5 scenarios: safe, H₂S buildup, O₂ depletion, sensor fault, mixed hazard
  - Realistic noise and gradual changes
  - CLI interface for standalone testing
  - Sensor status reporting

### Backend Infrastructure
- [x] **FastAPI Application** (`backend/app.py`)
  - WebSocket endpoint for live telemetry streaming
  - REST API for inspection records and site management
  - Scenario control endpoint for demo
  - Health check and documentation endpoints
  - CORS support for development

- [x] **State Store** (`backend/state_store.py`)
  - SQLite-based offline-first storage
  - Sites table with location and statistics
  - Inspections table with full readings and provenance
  - Sync status tracking (pending/synced)
  - Query methods for site history and aggregation

### Guidance Pipeline
- [x] **Guidance Generator** (`pipeline/guidance.py`)
  - Template-based guidance in Hindi and English
  - Prompt builder for LLM integration (ready for Genie)
  - Decision-to-explanation translation
  - Never makes safety decisions (only explains)
  - Fallback templates when LLM unavailable

- [x] **Voice Generator** (`pipeline/voice.py`)
  - TTS pipeline infrastructure
  - Placeholder audio generation
  - WAV format output
  - Ready for Meta MMS-TTS integration
  - 16kHz sample rate (standard for MMS-TTS)

### Dashboards
- [x] **Field Unit Dashboard** (`dashboard/field_unit.html`)
  - Large GO/CAUTION/NO-GO/UNKNOWN decision banner
  - 4-state color coding with animations
  - Real-time sensor cards with individual status
  - Guidance text display
  - Decision provenance panel (shows rule engine decided, not LLM)
  - Demo scenario controls
  - Offline indicator
  - WebSocket connection status

- [x] **City Layer Dashboard** (embedded in `backend/app.py`)
  - Site listing with statistics
  - Last inspection status per site
  - Hazard count tracking
  - Auto-refresh every 10 seconds
  - Clean tabular view

### Testing & Documentation
- [x] **Integration Tests** (`tests/test_integration.py`)
  - Full pipeline testing (probe → decision → guidance → voice)
  - Multi-language support verification
  - Scenario switching validation
  - Provenance tracking verification
  - 10 passing tests

- [x] **Launch Script** (`run.py`)
  - Backend server launcher
  - Test runner
  - Simulated probe standalone mode
  - Command-line interface

- [x] **Documentation**
  - `README.md`: Complete setup and usage guide
  - `DEMO.md`: 3-minute demo script with Q&A
  - `docs/project_overview.md`: Full system description
  - `docs/technical_architecture.md`: Implementation details
  - This status document

## ⚠️ Pending Components (Hardware/Model Integration)

### Hardware Integration
- [ ] **Arduino Probe Firmware** (`firmware/probe_node/`)
  - **Status**: Design complete, hardware not yet available
  - **Needs**: Arduino board + 4 gas sensors
  - **Tasks**:
    - Wire sensors to Arduino
    - Implement 2-second polling loop
    - Add LED/buzzer dead-man's-switch
    - USB serial output at 115200 baud
  - **Workaround**: Using simulated probe for development and demo

### AI Model Integration
- [ ] **Qualcomm Genie LLM**
  - **Status**: Infrastructure ready, model not compiled
  - **Needs**: 
    - Snapdragon X Elite hardware
    - QAIRT SDK ≥2.29.0
    - qai_hub_models package
  - **Tasks**:
    - Compile Llama-3.2-3B-Instruct via AI Hub
    - Generate Genie bundle (context binaries + config)
    - Update `guidance.py` to use actual Genie runtime
    - Benchmark CPU vs NPU latency
    - Add NPU visibility panel to dashboard
  - **Workaround**: Using template-based guidance (Hindi/English)

- [ ] **Meta MMS-TTS Model**
  - **Status**: Pipeline ready, model not downloaded
  - **Needs**: 
    - Download ONNX model from Hugging Face/MMS repository
    - Place in `models/tts/` directory
  - **Tasks**:
    - Download mms-tts-hin-female-medium.onnx (or similar)
    - Update `voice.py` to load model
    - Verify audio quality
    - Test with fp32 and fp16 (avoid naive INT8)
  - **License**: CC-BY-NC-4.0 (non-commercial only - document this)
  - **Workaround**: Using placeholder audio (2-second tone)

### Predictive Risk Layer
- [ ] **Tabular Risk Model**
  - **Status**: Design complete, not yet trained
  - **Needs**: Training data or synthetic scenarios
  - **Tasks**:
    - Gather/generate site history data
    - Feature engineering (season, days since cleaning, site type, past incidents)
    - Train gradient boosting or logistic regression model
    - Export model (joblib or ONNX)
    - Integrate with field unit for pre-entry risk flagging
  - **Note**: Must never override live sensor readings
  - **Workaround**: Not critical for demo - can be added later

## Test Results

### Unit Tests
```
90/90 tests passing
Coverage: Rule engine and safety thresholds fully tested
Runtime: < 1 second
```

### Integration Tests
```
10/10 tests passing
Coverage: Full pipeline, language support, simulated probe
Runtime: < 1 second
```

### System Test (Manual)
- [x] Backend starts without errors
- [x] Dashboard loads and connects via WebSocket
- [x] All 5 scenarios switch correctly
- [x] Real-time telemetry updates work
- [x] Offline mode works (DevTools network tab → offline)
- [x] Provenance panel shows correct sources
- [x] UNKNOWN state visually distinct from GO
- [x] City dashboard shows site statistics

## Demo Readiness

### ✅ Ready to Demo Now
- Complete end-to-end system with simulated hardware
- All decision logic working correctly
- Real-time dashboard with live updates
- Multi-language guidance (template-based)
- Offline operation
- Decision provenance tracking
- Comprehensive testing

### 🔧 Would Enhance Demo (Not Blockers)
- Physical Arduino probe with real sensors
- Actual Genie LLM generating guidance (vs templates)
- Spoken Hindi audio via MMS-TTS (vs placeholder)
- NPU usage visibility panel with benchmarks
- Predictive risk scoring for sites

## Deployment Checklist

### For Hackathon Submission
- [x] Public GitHub repository
- [x] Open-source license (specify in LICENSE file)
- [x] README with setup instructions
- [x] Comprehensive documentation
- [x] Working executable system
- [x] Test suite
- [x] Demo script

### For Pilot Deployment
- [ ] Real Arduino probe validated
- [ ] Cross-validation against certified gas meters
- [ ] Genie LLM integrated and benchmarked
- [ ] Field testing with ERSU team
- [ ] Hindi TTS validated by native speakers
- [ ] Packaging for Windows ARM64 (PyInstaller)
- [ ] Training materials for supervisors

### For Production Deployment
- [ ] Certification path identified (BIS standards)
- [ ] Replace MMS-TTS with commercial license
- [ ] Rugged probe housing tested in field conditions
- [ ] Battery life testing (multi-day operation)
- [ ] Calibration protocol established
- [ ] Integration with NAMASTE reporting systems
- [ ] Municipal pilot program complete

## Quick Start

```bash
# Install and test
pip install -r requirements.txt
python run.py test

# Start the system
python run.py backend

# Open dashboards
# Field Unit: http://localhost:8000/dashboard
# City Layer: http://localhost:8000/city
```

## Known Limitations

1. **Not a certified life-safety instrument**: This is a decision-support prototype. Real deployment requires cross-validation against certified meters and regulatory approval.

2. **Simulated probe only**: Hardware design is complete but physical implementation pending Arduino availability.

3. **Template-based guidance**: Using rule-based templates instead of actual LLM until Genie integration complete. Functionally equivalent for demo but less flexible.

4. **Placeholder audio**: TTS pipeline is ready but not generating real Hindi speech until MMS-TTS model integrated.

5. **No predictive risk model**: System works on live sensor data only. Predictive layer is designed but not trained.

6. **Non-commercial TTS license**: Meta MMS-TTS is CC-BY-NC-4.0. Must be replaced for commercial deployment.

## Next Steps (Priority Order)

1. **Test on Snapdragon X hardware** (if available)
   - Verify performance
   - Benchmark latency
   - Test offline mode on actual device

2. **Integrate Genie LLM**
   - Compile model via AI Hub
   - Update guidance pipeline
   - Add NPU visibility panel
   - Benchmark CPU vs NPU

3. **Add MMS-TTS model**
   - Download Hindi model
   - Integrate with voice pipeline
   - Test audio quality

4. **Arduino probe implementation**
   - Source hardware components
   - Flash firmware
   - Test sensor integration
   - Validate against simulated probe

5. **Demo video production**
   - Record 3-minute walkthrough
   - Show offline mode
   - Highlight provenance tracking
   - Demonstrate all scenarios

## Contact & Contributions

This is an active project addressing a documented life-safety problem. Contributions welcome, especially in:
- Arduino firmware development
- Field testing with municipal teams
- Translation to additional Indian languages
- Integration with NAMASTE reporting systems

---

**Summary**: The Praan system is functionally complete for demonstration purposes with a simulated probe. Core safety logic is production-quality (fully tested, deterministic, auditable). AI integration points are architected and ready for Genie/MMS-TTS models when hardware is available.
