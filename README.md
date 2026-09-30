# Praan

## A Snapdragon-powered offline safety hub for confined-space sanitation

> Today, workers may throw a stone into a manhole or watch for cockroaches before deciding whether the air is safe. Praan replaces that guesswork with a gas probe, deterministic safety rules, synchronized worker and supervisor screens, local-language guidance, and an offline data system running on an HP Snapdragon PC.

Praan is built for one job: **one crew, one opening, one auditable entry decision**.

The laptop is the local hub. It reads the probe, evaluates the atmosphere, controls the job state, explains the result in the worker's language, stores the inspection history, and serves the supervisor, worker and ward interfaces over a private local network.

**The rule engine decides safety. The session manager controls permissions. The local AI explains. The database helps the city learn.**

---

## Why this is a Snapdragon solution

Praan is designed for the exact environment where a Snapdragon-powered HP PC is useful:

- The field team may have unreliable or no internet access.
- A safety decision cannot wait for a cloud request or cloud model timeout.
- Municipal gas and site history should stay on a controlled local device.
- A single efficient laptop can run the hub, database, local model and browser interfaces.
- Qualcomm Genie/QNN is the intended acceleration path for local language guidance.
- The system can continue operating in template mode when a model bundle is unavailable.
- Runtime status is capability-detected: Praan only reports `genie` or `NPU` after a real local runtime and bundle are available.

The current repository includes the Genie runtime adapter and honest fallback reporting. The actual model export and NPU benchmark still require the Snapdragon HP laptop, Qualcomm SDK and a locally compiled model bundle. Praan never fakes an NPU result.

---

## What is implemented

The current working system includes:

- Four-gas simulated probe: H2S, CO, O2 and LEL.
- Safe, H2S buildup, O2 depletion, sensor fault and mixed-hazard scenarios.
- Deterministic `GO`, `CAUTION`, `NO_GO` and `UNKNOWN` decisions.
- Freshness, physical-range, sensor-health, stabilization and hysteresis checks in the live engine.
- Supervisor session state machine.
- HMAC-signed worker and supervisor tokens.
- Worker phone WebSocket connection.
- Supervisor WebSocket connection.
- One probe reader broadcasting the same frame to every client.
- Worker watchdog and NO SIGNAL behavior.
- Hindi, Punjabi and English worker-state messages.
- Supervisor Today, Live Site and Wrap-up views.
- Worker join flow with consent and language choice.
- Live crew presence, readings, trends, event timeline and controls.
- Hold, deploy, authorize, evacuate, all-clear and close actions.
- Offline SQLite sites and inspection history.
- Ward summary, needs-action list, schematic offline map and CSV export.
- Template guidance with runtime-detected Genie integration.
- AI provenance showing engine, provider, model, latency and cloud-request count.
- 100 passing tests through `python run.py test`.

The physical probe, native Genie bundle, measured NPU benchmark and certified field calibration remain hardware-dependent steps. They are described honestly in [STATUS.md](STATUS.md).

---

## The complete system loop

```text
Probe or simulator
       |
       v
Single hub reader on the Snapdragon HP PC
       |
       v
Deterministic rule engine
       |
       +--> Session manager --> Worker phones
       |                         Supervisor tablet/laptop
       |
       +--> SQLite history --> Ward view and CSV export
       |
       +--> Facts --> Template or local Genie explanation
                              |
                              v
                       Hindi/Punjabi/English guidance
```

The live path is intentionally ordered:

```text
measure -> verify -> decide -> authorize -> monitor -> log -> learn
```

The AI is downstream of the decision. It cannot turn a NO-GO into a GO.

---

## What happens in one job

1. The supervisor opens `/s` and chooses a site.
2. The hub creates a signed session and returns a worker join URL.
3. Workers open `/w?session=...&token=...`, select a language, give consent and tap Ready.
4. The worker sends `hello` to the hub over WebSocket.
5. The supervisor sees the worker in the crew list.
6. The supervisor deploys the probe.
7. One background task reads a probe frame every two seconds.
8. The rule engine evaluates freshness, sensor health, physical ranges, gas limits and trends.
9. The session manager updates the authoritative job state.
10. The supervisor receives a live snapshot over `/ws/supervisor`.
11. Each worker receives its canonical safety state over `/ws/worker`.
12. If a gas crosses a limit during entry, the job becomes EVACUATE and the workers receive the emergency state.
13. The session timeline records transitions, causes, actors and decision IDs.
14. Inspection data remains available in the local SQLite database.
15. The ward view aggregates the local history without cloud maps or cloud requests.

### Demo scenario

Use the supervisor's scenario control or the API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/simulate/scenario `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"scenario":"mixed_hazard"}'
```

The result should propagate through the same live path used by real probe input:

```text
simulated gas change
  -> rule decision
  -> session state
  -> supervisor telemetry
  -> worker safety screen
  -> event timeline
```

---

## Safety architecture

### One decision owner

Only the deterministic rule engine can produce:

```text
GO
CAUTION
NO_GO
UNKNOWN
```

The local LLM does not decide whether entry is allowed.

### Conservative failure behavior

- Missing data is not safe data.
- Faulty sensors produce `UNKNOWN`.
- Stale readings produce `UNKNOWN`.
- A NO-GO or UNKNOWN state during entry produces `EVACUATE`.
- A worker cannot self-authorize.
- Stable GO still requires supervisor authorization.
- A supervisor hold prevents authorization.
- Worker state defaults toward HOLD or STOP.

### Why the split matters

A generative model can be useful for:

- Explaining a measured H2S result simply.
- Rewriting an action plan in Hindi or Punjabi.
- Summarizing a timeline.
- Explaining why a site has a high historical priority.

It must not be used for:

- Deciding that the air is safe.
- Changing a gas limit.
- Creating a new emergency procedure.
- Telling a worker to ignore a NO-GO.
- Replacing a canonical STOP or EVACUATE instruction.

---

## Worker and supervisor connection design

### Worker messages

Workers may send only:

```json
{"type":"hello","name":"Ravi","lang":"hi","consent":true}
{"type":"loc","lat":28.61,"lon":77.21,"accuracy":18}
{"type":"ack","what":"entering"}
{"type":"ack","what":"exited"}
{"type":"hb"}
```

### Supervisor messages

Supervisor commands are authenticated and implemented through REST session commands:

```text
deploy_probe
hold
release_hold
authorize
evacuate
all_clear
close
```

### Supervisor snapshot

The supervisor receives a complete authoritative snapshot containing:

- Session state.
- Latest probe frame.
- Latest rule decision.
- Decision ID.
- Simulated/live flag.
- Worker list.
- Presence and entry status.
- Hold note.
- GO expiry.
- Timeline.

### Connection failure behavior

The worker has a client-side watchdog. If it receives no server message for six seconds, it shows `NO_SIGNAL` and does not keep showing an old GO state.

The probe reader is centralized so multiple browsers receive the same reading rather than competing for frames.

---

## Offline database and future intelligence

Praan uses SQLite locally through [backend/state_store.py](backend/state_store.py).

### Current stored data

The current store includes:

```text
sites
  site_id
  site_name
  location
  created_at
  last_inspection_ts

inspections
  inspection_id
  site_id
  timestamp
  decision
  risk_tier
  violated_thresholds
  readings_json
  guidance_text
  inspector_notes
  synced
```

A stored reading can contain:

```json
{
  "h2s_ppm": 14.2,
  "co_ppm": 18,
  "o2_pct": 19.8,
  "lel_pct": 2
}
```

The existing database can support three useful product functions.

### 1. Inspection record and complaint support

Each completed inspection can become an auditable local record for:

- Site safety complaints.
- Repeated unsafe-atmosphere reports.
- Supervisor incident review.
- Cleaning and maintenance follow-up.
- Ward-level operational planning.
- Export to a municipal system when connectivity returns.

A complaint or follow-up record should point to:

```text
site_id
inspection_id
session_id
timestamp
latest decision
violated gases
readings snapshot
supervisor
attached timeline
```

This lets a ward officer answer what happened at a site without relying on memory or a cloud dashboard.

### 2. History score

The database can compute a transparent site-priority score using:

```text
recent NO-GO rate
recent UNKNOWN rate
maximum and average H2S
minimum oxygen
sensor-fault rate
repeated dominant hazard
time since last cleaning
site type
```

The output should be labelled:

```text
history score (rule-based)
```

Example:

```text
MH-1049: HIGH PRIORITY
- 3 of the last 5 inspections were NO-GO
- H2S was the dominant hazard
- Cleaning is overdue
```

This score only prioritizes where the team should pay attention. It never overrides the live gas reading.

### 3. Offline predictive model

After enough historical data exists, a small local model can estimate the probability that a site will require extra attention before inspection.

Possible features:

```text
days_since_cleaning
nogo_count_last_5
unknown_count_last_5
h2s_mean_last_5
h2s_max_last_5
h2s_slope
minimum_o2_last_5
sensor_fault_rate
site_type
season
```

The model output should be:

```text
routine
watch
high priority
```

It must never be:

```text
safe to enter
```

The live deterministic engine remains the only entry decision-maker.

### Recommended next database table

For stronger trend analysis, add a per-reading table:

```sql
CREATE TABLE readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ts REAL NOT NULL,
    h2s_ppm REAL,
    co_ppm REAL,
    o2_pct REAL,
    lel_pct REAL,
    sensor_status_json TEXT,
    decision TEXT NOT NULL,
    decision_id TEXT,
    simulated INTEGER NOT NULL DEFAULT 1
);
```

That enables:

- H2S slope graphs.
- Ventilation before/after comparisons.
- Time-to-limit analysis.
- Incident reconstruction.
- Better site prioritization.
- CPU/NPU end-to-end demo metrics.

---

## Local AI and Qualcomm Genie path

### Current truth

On a fresh development machine, the status is:

```text
engine: template
provider: none
model: none
cloud_requests: 0
```

This is intentional. The application does not claim to use NPU without a real local runtime.

### Runtime adapter

[pipeline/genie_runtime.py](pipeline/genie_runtime.py) checks for:

```text
PRAAN_HOME
PRAAN_GENIE_BUNDLE
PRAAN_GENIE_COMMAND
PRAAN_GENIE_MODEL
PRAAN_GENIE_PROVIDER
PRAAN_GENIE_TIMEOUT_SECONDS
```

Genie is considered available only when:

1. A local command is configured.
2. The executable exists.
3. The Genie bundle exists.
4. The process can execute successfully.

When available, the status panel can report:

```text
engine: genie
provider: NPU or CPU
model: actual model name
latency_ms: measured value
```

### Snapdragon setup sequence

The human device setup is:

```powershell
python -c "import platform; print(platform.machine())"
```

The target output is ARM64.

Then:

1. Install ARM64 Python on the Snapdragon HP laptop.
2. Install the supported QAIRT/Genie runtime.
3. Install the current Qualcomm AI Hub model tooling.
4. Export a supported small instruct model for the target Snapdragon chipset.
5. Place the generated bundle under `%USERPROFILE%\Praan\models\genie` or set `PRAAN_GENIE_BUNDLE`.
6. Configure the local Genie runner command.
7. Run a prompt smoke test offline.
8. Start Praan and inspect `/api/ai/status`.
9. Confirm the provider is based on real runtime evidence.
10. Record measured latency and tokens per second.

The exact export command should follow the current Qualcomm documentation because model package names and supported device identifiers can change.

### Guidance pipeline

```text
rule decision
+ computed facts
+ role
+ language
        |
        v
canonical safety text immediately
        |
        v
optional Genie rewrite asynchronously
        |
        v
validator
        |
        +--> validated explanation
        |
        +--> canonical fallback
```

Critical worker messages such as STOP, HOLD and EVACUATE remain canonical and pre-authored. Genie cannot replace them.

---

## What to benchmark on the Snapdragon HP PC

The most meaningful benchmarks are not only language-model token numbers.

Measure:

```text
1. Rule-engine decision latency.
2. Probe-to-supervisor update latency.
3. Probe-to-worker state latency.
4. Sensor threshold crossing to worker red-screen latency.
5. Genie time to first token.
6. Genie end-to-end explanation latency.
7. Genie tokens per second.
8. CPU baseline versus NPU.
9. Battery drain during a 30-minute live session.
10. Cloud requests during the complete demo.
```

The final results file should contain only measured values. Until those values are collected, the README and presentation must say that NPU execution is pending validation.

---

## Interfaces

Start the hub:

```powershell
python run.py backend
```

Open:

```text
http://127.0.0.1:8000/s          Supervisor
http://127.0.0.1:8000/w          Worker entry point
http://127.0.0.1:8000/ward       Ward summary
http://127.0.0.1:8000/dashboard   Field telemetry
http://127.0.0.1:8000/city        Legacy city view
http://127.0.0.1:8000/docs        FastAPI API documentation
```

Run the tests:

```powershell
python run.py test
```

Expected current result:

```text
100 passed
```

### Important API routes

```text
POST /api/sessions
GET  /api/sessions/{id}/snapshot
GET  /api/sessions/{id}/timeline
POST /api/sessions/{id}/deploy_probe
POST /api/sessions/{id}/hold
POST /api/sessions/{id}/release_hold
POST /api/sessions/{id}/authorize
POST /api/sessions/{id}/evacuate
POST /api/sessions/{id}/all_clear
POST /api/sessions/{id}/close

GET  /api/sites
GET  /api/sites/{id}/history
GET  /api/ward/summary
GET  /api/ward/export.csv
GET  /api/ai/status
POST /api/simulate/scenario

WS /ws/worker
WS /ws/supervisor
WS /ws/telemetry
```

---

## File map

```text
backend/app.py                  FastAPI hub, routes and probe broadcast loop
backend/state_store.py          Offline SQLite sites and inspections
backend/simulated_probe.py      Five-scenario four-gas simulator
backend/ws_worker.py            Worker WebSocket protocol

safety/limits.yaml               Single safety configuration with human citation gates
safety/config.py                 Limits loader and citation validation
safety/engine_v2.py              Live stateful rule engine
safety/rule_engine.py            Original deterministic compatibility engine

session/manager.py               Authoritative session state machine
session/events.py                Append-only event log
session/auth.py                  HMAC token generation and validation

pipeline/guidance.py             Canonical/template/Genie explanation layer
pipeline/genie_runtime.py        Local Genie capability detection and execution
pipeline/voice.py                Voice pipeline placeholder

web/supervisor/index.html        Supervisor Today, Live Site and Wrap-up UI
web/worker/index.html            Worker phone UI
web/worker/worker.js             Worker socket, watchdog and actions
web/ward/index.html              Offline ward view

dashboard/field_unit.html        Legacy field telemetry dashboard
firmware/README.md               Physical probe plan

tests/unit/test_rule_engine.py   Boundary tests for safety decisions
tests/test_integration.py        Probe-to-guidance integration tests
STATUS.md                       Current implementation truth table
DEMO.md                         Three-minute presentation script
ARCHITECTURE.md                 System architecture reference
docs/technical_architecture.md  Deeper technical design
```

---

## Challenge alignment

### Technical implementation

- Local FastAPI hub designed for a Snapdragon HP laptop.
- Offline SQLite persistence.
- Browser clients connected over a private local network.
- Deterministic safety logic with tests and provenance.
- Qualcomm Genie runtime adapter with NPU/CPU status detection.
- Measurable latency and benchmark path.
- No dependency on a cloud LLM for a safety decision.

### Application use case and innovation

Praan combines:

```text
live gas verification
+ safety state machine
+ local-language worker guidance
+ supervisor authorization
+ offline history
+ ward-level operational intelligence
```

The historical database can support complaints, inspection records, repeated-hazard analysis and future site-priority models while live safety remains deterministic.

### Deployment and accessibility

- Plain browser interfaces.
- No app-store installation required.
- Local Wi-Fi operation.
- Worker phone flow.
- Supervisor laptop/tablet flow.
- Local-language messages.
- Offline ward summary.
- Simulator labelled clearly until hardware is attached.

### Presentation and documentation

The recommended judge demonstration is:

1. Open supervisor Today.
2. Start a job.
3. Open the worker join URL.
4. Show the worker in the supervisor crew list.
5. Deploy the probe.
6. Change to H2S buildup or mixed hazard.
7. Show telemetry, decision, worker state and timeline changing together.
8. Turn off external internet access.
9. Show that local operation continues.
10. Open the ward view and export CSV.
11. Show `/api/ai/status`.
12. When the model is installed, show measured Genie/NPU latency and cloud requests equal to zero.

---

## Honest limitations and next work

The current prototype is not a certified gas instrument and must not be presented as one.

Still required for a deployment-grade system:

- Human verification and citation of every safety limit.
- One canonical engine used by both tests and backend.
- Per-reading session persistence.
- Playbook-backed action assignment and validation.
- Full inspection persistence at wrap-up.
- Real Genie bundle and Snapdragon NPU measurements.
- Native-speaker review and recording of critical Hindi/Punjabi audio.
- Physical probe firmware, autonomous alarm and calibration.
- Windows ARM64 packaging and clean-machine testing.
- Real phone, Wi-Fi, Wake Lock and geolocation testing.
- Fault-injection rehearsal.

The simulator is not hidden. It is the current development and presentation instrument until the physical probe is available.

---

## Supporting documents

- [DEMO.md](DEMO.md): presentation script and judge questions.
- [STATUS.md](STATUS.md): current implementation status.
- [ARCHITECTURE.md](ARCHITECTURE.md): architecture diagrams and data flow.
- [docs/technical_architecture.md](docs/technical_architecture.md): deeper design notes.
- [firmware/README.md](firmware/README.md): physical probe plan.
- [.kiro/specs/snapdragon-npu-integration/requirements.md](.kiro/specs/snapdragon-npu-integration/requirements.md): detailed NPU integration requirements.

---

## Submission positioning

Praan should be presented as:

> An offline, Snapdragon-ready safety hub that replaces informal atmosphere checks with deterministic measurement, synchronized field coordination and local AI explanation. The system keeps the safety decision auditable while using the HP Snapdragon PC for the compute, privacy, responsiveness and future NPU acceleration needed in real sanitation work.

The core claim is not that an LLM is clever enough to decide safety.

The core claim is that local AI is being used responsibly inside a complete system where:

```text
rules protect the worker
sessions coordinate the crew
the database preserves evidence
AI improves explanation and prioritization
Snapdragon enables the whole loop to run locally
```
