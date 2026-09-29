# Requirements Document: Snapdragon NPU Integration

## Introduction

This specification defines the requirements for integrating Qualcomm Snapdragon NPU (Hexagon accelerator) support into the PRAAN crew-safety system for sewer workers. The integration addresses the critical competition criterion: real on-device AI inference using Genie LLM runtime on Snapdragon X Elite hardware. The system must maintain all safety invariants while adding measured NPU-accelerated guidance generation, fixing existing defects, and implementing the complete inspection workflow.

## Glossary

- **NPU**: Neural Processing Unit (Hexagon DSP accelerator on Snapdragon X Elite)
- **Genie**: Qualcomm AI Stack runtime for on-device LLM inference
- **Hub**: Field unit (Snapdragon laptop) that coordinates probe, rule engine, and worker devices
- **Probe**: Arduino-based 4-sensor gas detection unit (H₂S, CO, O₂, LEL)
- **Rule_Engine**: Deterministic safety decision logic (GO/CAUTION/NO_GO/UNKNOWN)
- **Worker_Phone**: Mobile device receiving real-time safety alerts via WebSocket
- **Session**: Inspection lifecycle from site selection through close-out
- **Guidance_Generator**: LLM-based component that translates rule-engine decisions to plain language
- **Canonical_Safety_Text**: Pre-translated, immutable safety messages (STOP/EVACUATE)
- **State_Store**: SQLite-based offline storage for inspections and site history
- **Field_UI**: Dashboard for on-site inspection (field_unit.html)
- **City_UI**: Municipal dashboard for aggregated site data
- **Simulation_Mode**: Development mode using SimulatedProbe instead of hardware

## Requirements

### Requirement 1: NPU-Accelerated LLM Inference

**User Story:** As a competition judge, I want to verify that the system uses real Snapdragon NPU hardware for AI inference, so that I can confirm the 40-point criterion is met.

#### Acceptance Criteria

1. WHEN the Guidance_Generator initializes with use_genie=True, THE Hub SHALL load the Llama-3.2-3B-Instruct model via Qualcomm Genie runtime
2. WHEN the Guidance_Generator loads the model, THE Hub SHALL configure Genie to use the Hexagon NPU backend
3. WHEN the Rule_Engine produces a safety decision, THE Guidance_Generator SHALL generate plain-language guidance using NPU inference
4. THE Guidance_Generator SHALL measure and log NPU inference latency for each generation
5. WHEN NPU inference completes, THE Hub SHALL include latency metrics in the guidance response (keys: inference_time_ms, backend_type)
6. IF the Genie runtime fails to initialize, THEN THE Guidance_Generator SHALL fall back to template mode and log a warning
7. THE Hub SHALL expose an endpoint GET /api/npu/status that returns NPU availability, backend type, and model name

### Requirement 2: Template Fallback Mode

**User Story:** As a system operator, I want the guidance system to work even if NPU hardware is unavailable, so that development and testing can proceed on non-Snapdragon devices.

#### Acceptance Criteria

1. WHEN the Guidance_Generator initializes with use_genie=False, THE Hub SHALL use template-based guidance generation
2. WHEN the Genie runtime fails to initialize, THE Guidance_Generator SHALL automatically fall back to template mode
3. WHILE operating in template mode, THE Guidance_Generator SHALL populate guidance messages from pre-defined templates (current _template_fallback implementation)
4. THE Hub SHALL include a mode indicator in all guidance responses (genie_active: true/false)
5. WHEN operating in template mode, THE Field_UI SHALL display a "SIMULATION MODE" badge

### Requirement 3: Safety Invariant Preservation

**User Story:** As a safety engineer, I want the rule engine to remain the sole authority for GO/NO_GO decisions, so that AI cannot override safety logic.

#### Acceptance Criteria

1. THE Rule_Engine SHALL be the exclusive decision source for GO/CAUTION/NO_GO/UNKNOWN states
2. THE Guidance_Generator SHALL NOT modify or override Rule_Engine decisions
3. WHEN the Guidance_Generator receives a Rule_Engine decision, THE Hub SHALL pass the decision unchanged to all connected clients
4. THE Hub SHALL include provenance metadata in every decision showing decision_source="deterministic_rule_engine" and explanation_source="on_device_llm" or "template"
5. IF the Guidance_Generator fails or times out, THEN THE Hub SHALL send the Rule_Engine decision with default template guidance

### Requirement 4: Guidance Generation Latency Targets

**User Story:** As a field operator, I want guidance messages to appear within 2 seconds of sensor readings, so that I can make timely safety decisions.

#### Acceptance Criteria

1. WHEN NPU inference is available, THE Guidance_Generator SHALL complete generation within 500ms (95th percentile)
2. WHEN operating in template mode, THE Guidance_Generator SHALL complete generation within 50ms
3. THE Hub SHALL measure end-to-end latency from probe reading to WebSocket delivery
4. IF guidance generation exceeds 2 seconds, THEN THE Hub SHALL send the Rule_Engine decision with a timeout indicator
5. THE Field_UI SHALL display a latency indicator showing time from reading to display

### Requirement 5: Multi-Language Guidance

**User Story:** As a Hindi-speaking sewer worker, I want safety instructions in my native language, so that I can understand hazard warnings clearly.

#### Acceptance Criteria

1. THE Guidance_Generator SHALL support language parameter with values: "en" (English) and "hi" (Hindi)
2. WHEN generating guidance in Hindi, THE Genie_LLM SHALL produce output in Devanagari script
3. THE Guidance_Generator SHALL preserve canonical safety text (STOP/EVACUATE/DO_NOT_ENTER) in pre-translated form
4. THE Hub SHALL include the language code in all guidance responses
5. WHERE the user selects a language preference, THE Field_UI SHALL send guidance requests with that language parameter

### Requirement 6: Scenario Testing API

**User Story:** As a demo presenter, I want to trigger different hazard scenarios instantly, so that I can show the system's response to various conditions.

#### Acceptance Criteria

1. THE Hub SHALL expose endpoint POST /api/simulate/scenario accepting a request body with field "scenario"
2. WHEN the endpoint receives a valid scenario name, THE Hub SHALL reconfigure the SimulatedProbe to that scenario
3. THE Hub SHALL validate scenario names against allowed values: "safe", "h2s_buildup", "o2_depletion", "sensor_fault", "mixed_hazard"
4. IF an invalid scenario name is provided, THEN THE Hub SHALL return HTTP 400 with error details
5. WHEN the scenario changes, THE Hub SHALL reset the SimulatedProbe start time to enable time-based progression

### Requirement 7: Inspection Recording Workflow

**User Story:** As a field supervisor, I want to record completed inspections with site context, so that the city layer can track hazard history.

#### Acceptance Criteria

1. WHEN the Field_UI submits an inspection via POST /api/inspection, THE State_Store SHALL save the inspection record to SQLite
2. THE State_Store SHALL capture these fields: site_id, site_name, decision, risk_tier, violated_thresholds, readings, guidance_text, inspector_notes
3. THE State_Store SHALL auto-generate inspection_id as a UUID and timestamp as Unix epoch
4. WHEN saving an inspection, THE State_Store SHALL update the site's last_inspection_ts field
5. THE State_Store SHALL mark all new inspections as unsynced (synced=0)

### Requirement 8: Site History Retrieval

**User Story:** As a field supervisor, I want to view a site's inspection history before entry, so that I can assess chronic hazard patterns.

#### Acceptance Criteria

1. THE Hub SHALL expose endpoint GET /api/sites returning all sites with summary statistics
2. WHEN querying all sites, THE State_Store SHALL calculate inspection_count and hazard_count per site
3. THE Hub SHALL expose endpoint GET /api/sites/{site_id}/history returning inspection records
4. THE State_Store SHALL order history records by timestamp descending (most recent first)
5. THE State_Store SHALL limit history results to 20 records by default

### Requirement 9: City Dashboard Population

**User Story:** As a municipal officer, I want the city dashboard to show aggregated site data, so that I can identify high-risk locations.

#### Acceptance Criteria

1. WHEN the City_UI loads, THE City_UI SHALL fetch all sites via GET /api/sites
2. THE City_UI SHALL display these columns: site_id, site_name, last_inspection (formatted timestamp), last_decision (badge), inspection_count, hazard_count
3. WHEN a site has last_decision set, THE City_UI SHALL render a color-coded badge (green=GO, yellow=CAUTION, red=NO_GO, gray=UNKNOWN)
4. THE City_UI SHALL auto-refresh site data every 10 seconds
5. IF no sites exist, THEN THE City_UI SHALL display "No sites recorded yet"

### Requirement 10: Real-Time WebSocket Updates

**User Story:** As a worker with a phone, I want to see live sensor updates within 1 second of probe readings, so that I have current safety information.

#### Acceptance Criteria

1. WHEN a client connects to /ws/telemetry, THE Hub SHALL accept the WebSocket connection
2. WHILE the connection is active, THE Hub SHALL poll the Probe every 2 seconds
3. WHEN the Hub receives a probe frame, THE Hub SHALL evaluate it via Rule_Engine and generate guidance within 200ms
4. THE Hub SHALL broadcast the combined update (frame, decision, guidance) to all connected WebSocket clients
5. IF a WebSocket client disconnects, THEN THE Hub SHALL clean up the connection without affecting other clients

### Requirement 11: Offline Operation

**User Story:** As a field operator in a location without network access, I want all safety functions to work offline, so that connectivity does not compromise safety.

#### Acceptance Criteria

1. THE Hub SHALL operate without internet connectivity (offline-first architecture)
2. THE Guidance_Generator SHALL run entirely on-device (no cloud API calls)
3. THE State_Store SHALL persist all inspections to local SQLite database
4. THE Field_UI SHALL connect to the Hub via LAN WebSocket (no internet required)
5. WHEN the browser detects offline status, THE Field_UI SHALL display an "OFFLINE MODE" indicator

### Requirement 12: Windows ARM64 Executable

**User Story:** As a competition judge with a Snapdragon X Elite device, I want a pre-built Windows ARM64 executable, so that I can run the system without manual setup.

#### Acceptance Criteria

1. THE Build_Pipeline SHALL use GitHub Actions with windows-11-arm runner
2. THE Build_Pipeline SHALL package the application using PyInstaller for ARM64 architecture
3. THE Executable SHALL bundle Python runtime, dependencies, and all assets (HTML, CSS, JS)
4. WHEN the Executable runs, THE Hub SHALL resolve asset paths using PyInstaller-compatible path logic (not __file__)
5. THE Build_Pipeline SHALL produce a single .exe artifact downloadable from GitHub Releases

### Requirement 13: Browser Voice Synthesis

**User Story:** As a worker receiving an alert, I want to hear spoken guidance, so that I can keep my eyes on the environment while receiving instructions.

#### Acceptance Criteria

1. WHEN the Field_UI receives guidance text, THE Field_UI SHALL synthesize speech using browser SpeechSynthesis API
2. WHERE the browser supports Hindi voices, THE Field_UI SHALL use a Hindi voice for Hindi guidance
3. IF no Hindi voice is available, THEN THE Field_UI SHALL use the default browser voice and log a warning
4. THE Field_UI SHALL provide a manual "Play Audio Guidance" button for replay
5. THE Field_UI SHALL auto-play critical alerts (NO_GO, UNKNOWN states) without user interaction

### Requirement 14: Probe Connection Indicator

**User Story:** As a field operator, I want to know if the probe is connected, so that I can troubleshoot hardware issues.

#### Acceptance Criteria

1. THE Hub SHALL track probe connection status (connected/disconnected)
2. WHEN the Hub starts with SimulatedProbe, THE Hub SHALL send mode="simulated" in the WebSocket status message
3. WHEN the Hub connects to a real Arduino probe, THE Hub SHALL send mode="hardware" in the WebSocket status message
4. IF the probe connection drops, THEN THE Hub SHALL broadcast a status update with connection_lost=true
5. THE Field_UI SHALL display connection status in the header badge (green="Connected", red="Disconnected")

### Requirement 15: Sensor Status Handling

**User Story:** As a safety system, I want to distinguish between "safe" and "unable to verify," so that sensor faults are treated as unsafe conditions.

#### Acceptance Criteria

1. WHEN any sensor reports status other than "ok", THE Rule_Engine SHALL return decision="UNKNOWN"
2. THE Rule_Engine SHALL populate violated_thresholds with fault details (e.g., "h2s_fault", "o2_missing")
3. THE Field_UI SHALL render UNKNOWN state with gray styling distinct from GO (green) and NO_GO (red)
4. THE Field_UI SHALL display per-sensor status badges showing "OK" or "FAULT"
5. WHEN a sensor fault occurs, THE Guidance_Generator SHALL produce text like "Cannot verify atmosphere. Do not enter."

### Requirement 16: Threshold Boundary Testing

**User Story:** As a safety engineer, I want all threshold boundaries tested, so that edge cases near limits are handled correctly.

#### Acceptance Criteria

1. THE Test_Suite SHALL include tests for values at exact thresholds (e.g., H₂S = 10.0 ppm for caution boundary)
2. THE Test_Suite SHALL include tests for values 0.1 units above and below each threshold
3. THE Test_Suite SHALL test oxygen's inverted logic (lower is worse) at all boundaries
4. THE Test_Suite SHALL verify that decision="CAUTION" is returned for caution-tier violations (not silently upgraded to GO)
5. THE Test_Suite SHALL achieve 100% branch coverage of rule_engine.py

### Requirement 17: Session State Machine

**User Story:** As a field supervisor, I want a structured inspection workflow, so that all steps from site selection to sign-off are tracked.

#### Acceptance Criteria

1. THE Hub SHALL maintain session state with values: PREP, SAMPLING, BLOCKED, READY, AUTHORIZED, IN_ENTRY, EVACUATE, CLOSING, CLOSED
2. WHEN a session starts, THE Hub SHALL initialize state to PREP
3. WHEN the Rule_Engine returns NO_GO, THE Hub SHALL transition session state to BLOCKED
4. WHEN the Rule_Engine returns GO, THE Hub SHALL transition session state to READY
5. THE Hub SHALL log all state transitions with timestamp and triggering event to the State_Store

### Requirement 18: Location Privacy

**User Story:** As a worker concerned about tracking, I want location to be optional and session-only, so that my movements are not permanently recorded.

#### Acceptance Criteria

1. THE Field_UI SHALL NOT require location permissions to operate
2. WHERE the user grants location access, THE Hub SHALL store location only for the active session
3. WHEN a session closes, THE Hub SHALL purge location data for that session
4. THE Hub SHALL mark all location fields as optional in the database schema
5. THE Field_UI SHALL display a notice: "Location is optional and used only for this session"

### Requirement 19: Simulated Data Labeling

**User Story:** As a competition judge, I want simulated data clearly labeled, so that I can distinguish demo mode from real hardware operation.

#### Acceptance Criteria

1. WHEN operating with SimulatedProbe, THE Field_UI SHALL display "SIMULATED DATA" badge on all sensor cards
2. THE Hub SHALL include a "mode" field in all WebSocket messages with value "simulated" or "hardware"
3. THE City_UI SHALL not display simulated inspections unless explicitly enabled via a debug flag
4. THE Field_UI SHALL color-code simulated data badges (orange background, white text)
5. WHEN switching from simulated to hardware, THE Hub SHALL broadcast a mode change notification

### Requirement 20: Hardcoded URL Fix

**User Story:** As a developer running the system on different ports, I want URLs to auto-detect the host and port, so that I don't get connection errors.

#### Acceptance Criteria

1. THE Field_UI SHALL construct WebSocket URLs using window.location.hostname and window.location.port
2. THE Field_UI SHALL construct API URLs using window.location.hostname and window.location.port
3. THE City_UI SHALL construct API URLs using window.location.hostname and window.location.port
4. THE Field_UI SHALL NOT contain hardcoded strings like "localhost:8000" or "192.168.1.100"
5. WHEN the Hub runs on port 9000, THE Field_UI SHALL connect to ws://{hostname}:9000/ws/telemetry

### Requirement 21: PyInstaller Path Resolution

**User Story:** As a packaged application, I want asset loading to work in both dev mode and .exe mode, so that the executable can find HTML/CSS/JS files.

#### Acceptance Criteria

1. THE Hub SHALL use sys._MEIPASS for base path resolution when running as a PyInstaller executable
2. THE Hub SHALL fall back to Path(__file__).parent when running as a Python script
3. THE Hub SHALL resolve dashboard file paths relative to the computed base path
4. THE Hub SHALL validate that dashboard/field_unit.html exists at startup and log an error if missing
5. THE Build_Pipeline SHALL verify asset inclusion by listing bundled files in the .exe

### Requirement 22: Global Probe Instance Fix

**User Story:** As a multi-client system, I want each WebSocket connection to read from the same probe instance, so that all clients see identical readings.

#### Acceptance Criteria

1. THE Hub SHALL instantiate a single SimulatedProbe at module level
2. WHEN multiple WebSocket clients connect, THE Hub SHALL serve readings from the shared probe instance
3. WHEN a scenario change occurs via POST /api/simulate/scenario, THE Hub SHALL update the shared probe instance
4. THE Hub SHALL broadcast scenario changes to all connected WebSocket clients
5. THE Hub SHALL NOT create per-client probe instances

### Requirement 23: NPU Metrics Endpoint

**User Story:** As a competition judge, I want to see measured NPU performance metrics, so that I can verify the NPU is actually being used.

#### Acceptance Criteria

1. THE Hub SHALL expose endpoint GET /api/npu/metrics returning aggregated performance data
2. THE Hub SHALL track these metrics: total_inferences, avg_latency_ms, p95_latency_ms, p99_latency_ms, backend_type
3. WHEN Genie is active, THE Hub SHALL record per-inference latency to compute percentiles
4. THE Hub SHALL reset metrics on server restart (no persistent storage required)
5. THE Field_UI SHALL display NPU metrics in a collapsible panel

### Requirement 24: Oxygen Upper Limit

**User Story:** As a safety system, I want to detect abnormally high oxygen levels, so that I can warn about oxygen-enriched atmospheres (fire risk).

#### Acceptance Criteria

1. THE Rule_Engine SHALL evaluate oxygen readings against an upper threshold (23% O₂)
2. WHEN O₂ exceeds 23%, THE Rule_Engine SHALL classify as "caution" tier
3. WHEN O₂ exceeds 25%, THE Rule_Engine SHALL classify as "hazard" tier
4. THE Rule_Engine SHALL add "o2_pct_high" to violated_thresholds for high oxygen
5. THE Guidance_Generator SHALL produce text like "Oxygen-enriched atmosphere. Fire risk. Use caution."

### Requirement 25: Guidance Prompt Template

**User Story:** As an AI engineer, I want a well-structured prompt template, so that LLM guidance is consistent and accurate.

#### Acceptance Criteria

1. THE Guidance_Generator SHALL use a system prompt stating "You translate a safety decision into one short, clear instruction. You do not make the decision."
2. THE Guidance_Generator SHALL include decision, risk_tier, and violated_thresholds in the user prompt
3. THE Guidance_Generator SHALL specify target language in the prompt (e.g., "Respond in Hindi (हिंदी)")
4. THE Guidance_Generator SHALL limit output to 2 sentences maximum
5. THE Guidance_Generator SHALL NOT include reassurances contradicting the decision (e.g., "but don't worry" in a NO_GO case)

### Requirement 26: Round-Trip Testing for Guidance Serialization

**User Story:** As a developer, I want guidance objects to serialize/deserialize correctly, so that WebSocket clients receive valid JSON.

#### Acceptance Criteria

1. FOR ALL valid guidance objects, serializing to JSON then deserializing SHALL produce an equivalent object (round-trip property)
2. THE Test_Suite SHALL verify that json.dumps(guidance) produces parseable JSON
3. THE Test_Suite SHALL verify that json.loads(json.dumps(guidance)) preserves all keys: ts, language, text, audio_ready
4. THE Test_Suite SHALL test guidance objects for all four decision states (GO, CAUTION, NO_GO, UNKNOWN)
5. THE Test_Suite SHALL test guidance with Unicode text (Devanagari script for Hindi)

### Requirement 27: Genie Model Compilation

**User Story:** As a developer preparing for deployment, I want to compile Llama-3.2-3B-Instruct for Snapdragon NPU, so that the model runs efficiently on Hexagon.

#### Acceptance Criteria

1. THE Build_Pipeline SHALL compile Llama-3.2-3B-Instruct using Qualcomm Genie SDK
2. THE Build_Pipeline SHALL target Hexagon NPU backend (not CPU fallback)
3. THE Build_Pipeline SHALL produce a context binary bundle with compiled weights and config
4. THE Guidance_Generator SHALL load the compiled model from the bundle path
5. THE Build_Pipeline SHALL log compilation success and model size (MB)

### Requirement 28: Error Message Clarity

**User Story:** As a field operator encountering an error, I want clear error messages, so that I can understand what went wrong and how to fix it.

#### Acceptance Criteria

1. WHEN the Hub fails to connect to the Probe, THE Hub SHALL log "Probe connection failed: [reason]"
2. WHEN Genie initialization fails, THE Guidance_Generator SHALL log "Genie runtime unavailable: [reason]. Falling back to template mode."
3. WHEN a WebSocket client sends invalid JSON, THE Hub SHALL return a structured error with field "error" and "details"
4. WHEN POST /api/simulate/scenario receives an invalid scenario, THE Hub SHALL return HTTP 400 with message "Invalid scenario. Choose from: [list]"
5. THE Field_UI SHALL display backend errors in a toast notification, not as browser alerts

### Requirement 29: Audit Log for Safety Decisions

**User Story:** As a safety auditor, I want all decisions logged with provenance, so that I can review the decision trail in case of an incident.

#### Acceptance Criteria

1. THE Hub SHALL log every Rule_Engine decision to a file safety_audit.log
2. THE Audit_Log SHALL include these fields: timestamp, decision, risk_tier, violated_thresholds, provenance, session_id
3. THE Audit_Log SHALL use structured JSON format (one JSON object per line)
4. THE Audit_Log SHALL NOT be editable via API (append-only)
5. THE Hub SHALL rotate the audit log daily, keeping 30 days of history

### Requirement 30: Calibration Record Integration

**User Story:** As a compliance officer, I want to track probe calibration dates, so that I can ensure equipment meets inspection standards.

#### Acceptance Criteria

1. THE State_Store SHALL add a calibration_log table with fields: probe_id, calibration_date, calibrated_by, next_due_date
2. THE Hub SHALL expose endpoint POST /api/probe/calibration to record calibration events
3. THE Field_UI SHALL display a warning banner if next_due_date is in the past
4. THE Hub SHALL include last_calibration_date in GET /api/npu/status response
5. THE Hub SHALL refuse to start an inspection session if the probe is overdue for calibration
