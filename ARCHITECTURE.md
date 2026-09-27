# Praan System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FIELD UNIT (Snapdragon X)                 │
│                                                                   │
│  ┌───────────┐      ┌──────────────┐      ┌─────────────────┐  │
│  │  Probe    │      │ Rule Engine  │      │   Dashboard     │  │
│  │ (Arduino) │─────→│(Deterministic│─────→│  (WebSocket)    │  │
│  │  4 Sensors│ USB  │   Decision)  │      │  Live Updates   │  │
│  └───────────┘      └──────────────┘      └─────────────────┘  │
│                             │                                     │
│                             ↓                                     │
│                      ┌──────────────┐                            │
│                      │  LLM (Genie) │                            │
│                      │  Explanation │                            │
│                      └──────────────┘                            │
│                             │                                     │
│                             ↓                                     │
│                      ┌──────────────┐                            │
│                      │ TTS (MMS)    │                            │
│                      │ Voice Output │                            │
│                      └──────────────┘                            │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    SQLite (Offline Storage)                │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Sync when online
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                   CITY LAYER (Municipal Office)                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Aggregated Site Data │ Hazard Maps │ ERSU Dispatch       │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow: Probe to Decision

```
1. PROBE READING
   ┌──────────────────────────────┐
   │ Arduino + 4 Gas Sensors      │
   │ - H₂S: 45 ppm                │
   │ - CO: 5 ppm                  │
   │ - O₂: 19.0%                  │
   │ - LEL: 8%                    │
   │ - All sensors: OK            │
   └──────────────────────────────┘
              │ USB Serial (JSON)
              ↓
2. RULE ENGINE EVALUATION
   ┌──────────────────────────────┐
   │ safety/rule_engine.py        │
   │ ┌──────────────────────────┐ │
   │ │ H₂S > 20 ppm? → HAZARD   │ │
   │ │ O₂ < 19.5%?  → HAZARD    │ │
   │ │ LEL > 5%?    → CAUTION   │ │
   │ └──────────────────────────┘ │
   │ WORST TIER: HAZARD           │
   │ DECISION: NO-GO              │
   └──────────────────────────────┘
              │
              ↓
3. PROVENANCE RECORD
   ┌──────────────────────────────┐
   │ Decision Source:             │
   │ ✓ deterministic_rule_engine  │
   │ ✗ llm (never)                │
   │                              │
   │ Explanation Source:          │
   │ ✓ on_device_llm              │
   │                              │
   │ Sensors: 4/4 operational     │
   └──────────────────────────────┘
              │
              ↓
4. LLM GUIDANCE GENERATION
   ┌──────────────────────────────┐
   │ pipeline/guidance.py         │
   │ Input: Decision + Readings   │
   │ Prompt: Translate to Hindi   │
   │ Output: "अंदर मत जाइए।      │
   │          H₂S खतरनाक स्तर   │
   │          पर है।"             │
   └──────────────────────────────┘
              │
              ↓
5. VOICE SYNTHESIS
   ┌──────────────────────────────┐
   │ pipeline/voice.py            │
   │ TTS Model: Meta MMS-TTS      │
   │ Language: Hindi              │
   │ Output: WAV audio file       │
   └──────────────────────────────┘
              │
              ↓
6. DASHBOARD DISPLAY
   ┌──────────────────────────────┐
   │ ┌──────────────────────────┐ │
   │ │       NO-GO              │ │
   │ │    (Red, Pulsing)        │ │
   │ └──────────────────────────┘ │
   │                              │
   │ H₂S: 45 ppm [HAZARD]         │
   │ O₂:  19.0% [HAZARD]          │
   │ LEL: 8% [CAUTION]            │
   │                              │
   │ 🔊 "अंदर मत जाइए..."        │
   └──────────────────────────────┘
```

## The Four Decision States

```
┌─────────────────────────────────────────────────────────────────┐
│                         DECISION STATES                          │
└─────────────────────────────────────────────────────────────────┘

1. GO (Green)
   ├─ All readings within safe limits
   ├─ All sensors operational
   └─ Entry permitted

2. CAUTION (Yellow/Orange)
   ├─ One or more readings approaching threshold
   ├─ Not yet hazardous
   └─ Action: Re-test before proceeding, alert supervisor

3. NO-GO (Red, Pulsing)
   ├─ Hazardous or extreme conditions detected
   ├─ H₂S, CO, LEL above thresholds OR O₂ below threshold
   └─ Action: Do not enter, notify supervisor immediately

4. UNKNOWN (Gray)
   ├─ Sensor fault or missing data
   ├─ Atmosphere CANNOT BE VERIFIED
   ├─ NOT the same as "safe"
   └─ Action: Do not enter, check equipment
```

## Safety Decision Logic (OSHA/NIOSH Thresholds)

```
GAS               SAFE     CAUTION   HAZARD    EXTREME
─────────────────────────────────────────────────────────
H₂S (ppm)        < 10      10-20     20-100     > 100
CO (ppm)         < 35      35-100    100-200    > 200
O₂ (%)           > 20.5    19.5-20.5 16-19.5    < 16    ← INVERTED
LEL (%)          < 5       5-10      10-20      > 20

DECISION LOGIC:
- If ANY sensor is faulty           → UNKNOWN
- If worst tier is "extreme"        → NO-GO (extreme)
- If worst tier is "hazard"         → NO-GO (hazard)
- If worst tier is "caution"        → CAUTION
- If all readings safe              → GO
```

## The Rule Engine vs LLM Split

```
┌─────────────────────────────────────────────────────────────────┐
│               WHO DECIDES WHAT (AND WHY)                         │
└─────────────────────────────────────────────────────────────────┘

RULE ENGINE (Deterministic, Auditable)
├─ Reads sensor values
├─ Compares against OSHA/NIOSH thresholds
├─ Checks sensor health
├─ Produces GO/CAUTION/NO-GO/UNKNOWN
└─ THIS IS THE SAFETY DECISION
    ↓
    Decision is FINAL and LOGGED
    ↓
LLM (Generative, Explanatory)
├─ Receives the ALREADY-MADE decision
├─ Receives sensor readings for context
├─ Translates to plain language (Hindi/English)
├─ Produces short, clear instruction
└─ THIS IS ONLY AN EXPLANATION
    ↓
    If LLM fails, show raw rule-engine decision
    Never let LLM failure block safety information
```

## Offline Operation

```
┌─────────────────────────────────────────────────────────────────┐
│                   OFFLINE-FIRST ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────┘

FIELD UNIT (ALWAYS WORKS)
├─ Probe → Rule Engine → Decision (no network needed)
├─ LLM Guidance (on-device via Genie, no cloud call)
├─ TTS Voice (on-device via MMS-TTS)
├─ Dashboard (local WebSocket, no internet)
└─ SQLite (local inspection storage)

SYNC WHEN ONLINE
├─ Background upload to city layer
├─ Conflict resolution (last-write-wins for now)
└─ Sync status tracked (pending/synced flag)

WHY THIS MATTERS
├─ Sewers/manholes often have poor connectivity
├─ A safety decision cannot wait for network timeout
├─ Data sovereignty (municipal data stays on-device)
└─ Battery life (no constant cloud polling)
```

## Component File Map

```
praan/
├── safety/                    [MOST CRITICAL CODE]
│   ├── thresholds.py          ← OSHA/NIOSH reference values
│   └── rule_engine.py         ← GO/CAUTION/NO-GO/UNKNOWN logic
│
├── backend/
│   ├── app.py                 ← FastAPI server, WebSocket
│   ├── state_store.py         ← SQLite offline storage
│   └── simulated_probe.py     ← Hardware simulator (5 scenarios)
│
├── pipeline/
│   ├── guidance.py            ← LLM prompt + Genie integration
│   └── voice.py               ← TTS pipeline (MMS-TTS ready)
│
├── dashboard/
│   └── field_unit.html        ← Real-time dashboard UI
│
├── firmware/                  [PENDING HARDWARE]
│   └── probe_node/            ← Arduino firmware (design complete)
│
├── tests/
│   ├── unit/
│   │   └── test_rule_engine.py  ← 90 tests, all boundaries
│   └── test_integration.py      ← Full pipeline tests
│
├── docs/
│   ├── project_overview.md      ← Full system description
│   └── technical_architecture.md ← Implementation details
│
├── run.py                       ← Launch script
├── requirements.txt             ← Dependencies
├── README.md                    ← Setup & usage
├── DEMO.md                      ← 3-minute demo script
├── IMPLEMENTATION_STATUS.md     ← What's done, what's pending
└── ARCHITECTURE.md              ← This file
```

## Tech Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                         TECHNOLOGY STACK                         │
└─────────────────────────────────────────────────────────────────┘

HARDWARE
├─ Probe: Arduino + 4 gas sensors (H₂S, CO, O₂, LEL)
├─ Field Unit: Snapdragon X Elite laptop
└─ City Layer: Any PC (can be same Snapdragon device)

LANGUAGES
├─ Backend: Python 3.11+
├─ Firmware: C++ (Arduino)
├─ Dashboard: HTML/CSS/JavaScript
└─ Guidance Output: Hindi + English (expandable)

FRAMEWORKS & LIBRARIES
├─ FastAPI + Uvicorn (backend server)
├─ WebSocket (real-time telemetry)
├─ SQLite (offline storage)
├─ pytest (testing)
├─ Qualcomm Genie (LLM runtime, when integrated)
├─ ONNX Runtime (TTS inference)
└─ numpy, scipy (audio processing)

AI MODELS (WHEN INTEGRATED)
├─ LLM: Llama-3.2-3B-Instruct (via Qualcomm Genie)
├─ TTS: Meta MMS-TTS (ONNX, Hindi voice)
└─ Predictive: sklearn gradient boosting (planned)

STANDARDS & REFERENCES
├─ OSHA PEL (Permissible Exposure Limits)
├─ NIOSH IDLH (Immediately Dangerous to Life or Health)
└─ OSHA 29 CFR 1910.146 (Confined Space Standard)
```

## Deployment Tiers

```
┌─────────────────────────────────────────────────────────────────┐
│                       DEPLOYMENT TIERS                           │
└─────────────────────────────────────────────────────────────────┘

TIER 1: Hackathon Demo (CURRENT STATUS)
├─ ✅ Simulated probe
├─ ✅ Rule engine + full testing
├─ ✅ Template-based guidance
├─ ✅ Dashboard (field + city)
├─ ✅ Offline operation
└─ ✅ Complete documentation

TIER 2: Pilot Deployment (NEXT STEPS)
├─ ⚠️ Real Arduino probe
├─ ⚠️ Genie LLM integrated
├─ ⚠️ MMS-TTS voice output
├─ ⚠️ Field testing with ERSU team
└─ ⚠️ Cross-validation with certified meters

TIER 3: Production Deployment (FUTURE)
├─ ❌ Regulatory certification (BIS standards)
├─ ❌ Commercial TTS license
├─ ❌ Rugged probe housing
├─ ❌ Multi-city deployment
└─ ❌ NAMASTE scheme integration
```

## Critical Design Decisions

### Why Deterministic Rule Engine?
- Auditable by safety inspectors
- No "black box" in life-safety decision path
- Threshold citations from published standards
- Testable with 100% coverage
- Fast (microseconds, not milliseconds)

### Why Separate LLM from Safety Decision?
- LLMs can hallucinate
- A safety decision cannot be "probably correct"
- If LLM fails, raw decision still displays
- Provenance tracking proves the split

### Why Four States (Not Binary)?
- CAUTION captures borderline readings
- UNKNOWN is distinct from NO-GO
- Prevents false sense of security from missing data
- Supervisor can re-test CAUTION, must not enter UNKNOWN

### Why Offline-First?
- Many sewer sites have poor connectivity
- Battery life matters (no cloud polling)
- Data sovereignty (municipal infrastructure data)
- Reliability (network timeout cannot block a life-safety alert)

### Why Snapdragon?
- On-device LLM inference (no cloud latency)
- NPU acceleration for local AI
- Multi-day battery life
- Proven in field-rugged devices

---

**For detailed implementation notes, see**:
- `docs/technical_architecture.md` - Full technical spec
- `IMPLEMENTATION_STATUS.md` - What's done, what's pending
- `README.md` - Setup and quick start
- `DEMO.md` - How to present this system
