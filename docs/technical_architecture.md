# Technical Architecture & Implementation Spec

*The engineering detail underneath the roadmap: sensor design, the safety-first rule/LLM split, the Genie-based guidance pipeline, local-language voice output, and the test plan for a device where a wrong answer costs a life.*

---

## CONTENTS

1. [Toolchain & environment matrix](#1-toolchain--environment-matrix)
2. [Repository structure](#2-repository-structure)
3. [Data contracts](#3-data-contracts)
4. [The rule engine — deterministic, auditable, first](#4-the-rule-engine--deterministic-auditable-first)
5. [The predictive risk layer](#5-the-predictive-risk-layer)
6. [Guidance generation via Genie](#6-guidance-generation-via-genie)
7. [Local-language voice output](#7-local-language-voice-output)
8. [Probe firmware & protocol](#8-probe-firmware--protocol)
9. [Field unit & city dashboard](#9-field-unit--city-dashboard)
10. [Packaging internals](#10-packaging-internals)
11. [Testing & validation plan](#11-testing--validation-plan)
12. [Benchmarking methodology](#12-benchmarking-methodology)
13. [Failure modes & fallback logic](#13-failure-modes--fallback-logic)
14. [Appendix: dependency pins](#14-appendix-dependency-pins)

---

## 1. Toolchain & environment matrix

| Component | Requirement | Why it matters |
|---|---|---|
| OS | Windows 11, ARM64, on the target Snapdragon HP device | QNN inference and PyInstaller's ARM64 bootloader both require native ARM64, not emulated x64. |
| Python (device) | 3.11 or 3.12, ARM64 build | Matches the AI Hub compile target exactly to avoid silent CPU fallback. |
| QAIRT SDK (Genie) | ≥ 2.29.0 | Earlier versions have documented issues with longer prompts; this is a hard minimum for the guidance pipeline. |
| qai-hub-models | latest, with the target model's extra installed | Drives the AI Hub compile job that produces Genie-compatible context binaries. |
| Microcontroller toolchain | Arduino Core / STM32Cube, whichever matches your chosen board | Probe firmware — kept deliberately simple and separate from the AI stack. |
| CI runner (packaging) | windows-11-arm GitHub-hosted runner | Produces a genuine native ARM64 .exe without owning hardware full-time. |

---

## 2. Repository structure

```
praan/
├── firmware/
│   └── probe_node/              # sensor polling, local LED/buzzer dead-man's-switch
├── safety/
│   ├── thresholds.py            # cited OSHA/NIOSH exposure limits, single source of truth
│   └── rule_engine.py           # deterministic GO/NO-GO logic — pure Python, no models
├── models/
│   ├── predictive/              # tabular risk model, training script, feature notes
│   ├── genie_bundle/            # LLM context binaries + tokenizer + genie_config.json (not in git — see §10)
│   └── tts/                     # MMS-TTS ONNX model(s), one per supported language
├── pipeline/
│   ├── guidance.py              # prompt builder + Genie call wrapper
│   └── voice.py                 # TTS wrapper
├── backend/
│   ├── app.py                   # FastAPI app, field-unit + city-layer endpoints
│   └── state_store.py
├── dashboard/                   # field-unit UI + city hazard map UI
├── tests/
│   ├── unit/                    # rule engine test table — the most important tests in this repo
│   └── hardware_in_loop/
├── benchmarks/
├── .github/workflows/build.yml
├── LICENSE
└── README.md
```

---

## 3. Data contracts

### 3.1 Probe telemetry frame (probe → field unit, USB-serial)

```json
{
  "ts": 1758100000,
  "h2s_ppm": 12.4,
  "co_ppm": 8.1,
  "o2_pct": 19.4,
  "lel_pct": 3.2,
  "sensor_status": {
    "h2s": "ok",
    "co": "ok",
    "o2": "ok",
    "lel": "ok"
  },
  "probe_depth_m": 4.2
}
```

Every sensor reports its own status independently. A single sensor reporting anything other than `"ok"` is enough to force a NO-GO — see §4.

### 3.2 Rule-engine decision (rule engine → guidance + dashboard)

```json
{
  "ts": 1758100000.2,
  "decision": "NO_GO",       // "GO" | "CAUTION" | "NO_GO" | "UNKNOWN"
  "risk_tier": "extreme",    // "safe" | "caution" | "hazard" | "extreme" | "unknown"
  "violated_thresholds": ["h2s_ppm", "o2_pct"],
  "readings": { "...": "the §3.1 frame, passed through" },
  "provenance": {
    "decision_source": "deterministic_rule_engine",   // never "llm" — this field should
                                                       // be structurally impossible to set
                                                       // to anything model-generated
    "explanation_source": "on_device_llm",
    "sensors_operational": "4/4",
    "reading_age_sec": 2
  }
}
```

The four-state decision matters: a binary safe/unsafe is less honest than the sensors actually are. **CAUTION** means readings are approaching a threshold or unstable — re-test, don't hard-stop. **UNKNOWN** means a sensor fault or dropped reading means the atmosphere cannot be verified at all — and it must never be allowed to render identically to a stable "safe" state in the UI. The provenance block exists specifically so the dashboard can show, without any extra computation, that a human-auditable rule made the call and the model only explained it.

### 3.3 Guidance message (LLM output → voice + dashboard)

```json
{
  "ts": 1758100000.6,
  "language": "hi",
  "text": "Zone mein H2S ka star khatarnak hai. Andar mat jaayein. Supervisor ko turant suchit karein.",
  "audio_ready": true
}
```

Keep §3.2 and §3.3 as separate stages in your pipeline, always logged separately. If a judge or auditor ever needs to know "did the AI decide this, or just explain it," the log should answer that instantly.

---

## 4. The rule engine — deterministic, auditable, first

**This is the most important file in the entire repository.** Build and test it before writing a single line of model code.

```python
# safety/thresholds.py — cite your source for every number

THRESHOLDS = {
    "h2s_ppm":  {"caution": 10,   "hazard": 20,   "extreme": 100},   # NIOSH IDLH: 100 ppm
    "co_ppm":   {"caution": 35,   "hazard": 100,  "extreme": 200},   # OSHA PEL / IDLH reference
    "o2_pct":   {"caution": 20.5, "hazard": 19.5, "extreme": 16},    # normal ~20.9%; below 19.5% is OSHA-deficient
    "lel_pct":  {"caution": 5,    "hazard": 10,   "extreme": 20},    # % of lower explosive limit
}

def evaluate(frame: dict, sensors_ok: int = 4) -> dict:
    provenance = {"decision_source": "deterministic_rule_engine",
                  "explanation_source": "on_device_llm",
                  "sensors_operational": f"{sensors_ok}/4"}

    # Any sensor NOT reporting "ok" -> UNKNOWN.  This is a distinct state from
    # NO_GO: it means "we cannot verify," not "we verified and it's dangerous."
    # It must never render identically to a stable GO in the UI.
    if any(s != "ok" for s in frame["sensor_status"].values()):
        return {"decision": "UNKNOWN", "risk_tier": "unknown",
                "violated_thresholds": ["sensor_fault"],
                "provenance": provenance}

    violations = []
    for key, limits in THRESHOLDS.items():
        value = frame[key]
        if key == "o2_pct":                       # oxygen is inverted: LOWER is worse
            if   value < limits["extreme"]:  violations.append((key, "extreme"))
            elif value < limits["hazard"]:   violations.append((key, "hazard"))
            elif value < limits["caution"]:  violations.append((key, "caution"))
        else:
            if   value > limits["extreme"]:  violations.append((key, "extreme"))
            elif value > limits["hazard"]:   violations.append((key, "hazard"))
            elif value > limits["caution"]:  violations.append((key, "caution"))

    if not violations:
        return {"decision": "GO", "risk_tier": "safe",
                "violated_thresholds": [], "provenance": provenance}

    worst = max(violations, key=lambda v: ["caution","hazard","extreme"].index(v[1]))

    # CAUTION is now its own decision state, not silently folded into GO —
    # a supervisor should be told to re-test, not given a clean green light.
    decision = {"caution": "CAUTION", "hazard": "NO_GO", "extreme": "NO_GO"}[worst[1]]

    return {"decision": decision, "risk_tier": worst[1],
            "violated_thresholds": [v[0] for v in violations],
            "provenance": provenance}
```

### Test this function harder than anything else in the project

Write a test table covering every threshold boundary, every sensor-fault combination, and multiple simultaneous violations — across all four decision states, not just GO/NO_GO. This function is the one piece of the whole system where a bug is not a bad user experience — it's a false "safe."

---

## 5. The predictive risk layer

A small, interpretable tabular model (gradient-boosted trees are a reasonable default) trained on whatever site-history features you can assemble: season, days since last cleaning, chamber type, past incident flags at that specific location. Its job is narrow — flag likely-hazardous sites for priority probing and ERSU scheduling — and it must never override the rule engine's live-sensor decision.

### Be honest about training data

Real historical incident data at the municipal level may be sparse, inconsistent, or simply not available to you during a hackathon timeline. If you bootstrap with synthetic or scenario-based data, say so plainly in the README. An honest "trained on synthetic scenarios pending real incident data" is a stronger technical claim than an implied, unverifiable accuracy number.

---

## 6. Guidance generation via Genie

This follows the same corrected path established for the earlier version of this project: decoder-only LLMs on Snapdragon are compiled as split QNN context binaries and run through Qualcomm's Genie runtime, not through a plain ONNX Runtime session call.

```bash
pip install "qai_hub_models[llama-v3-2-3b-chat-quantized]"

python -m qai_hub_models.models.llama_v3_2_3b_chat_quantized.export \
  --device "Snapdragon X Elite CRD" \
  --skip-inferencing --skip-profiling \
  --output-dir models/genie_bundle
```

The prompt template matters more here than in most applications, because the output is read or spoken directly to someone deciding whether to enter a hazardous space:

```python
SYSTEM_PROMPT = """You translate a safety decision into one short, clear instruction.
You do not make the decision — it has already been made.
Never contradict the decision given to you.
Never add reassurance the decision does not support.
Output at most two sentences."""

def build_prompt(rule_decision: dict, language: str) -> str:
    return f"""Decision: {rule_decision['decision']}
Risk tier: {rule_decision['risk_tier']}
Reason: {', '.join(rule_decision['violated_thresholds']) or 'none'}
Respond in {language}."""
```

Run it via `genie-t2t-run` for a first smoke test, then wrap the same call in your backend's guidance worker thread — see the earlier companion spec for the full CLI-vs-AppBuilder comparison, which applies unchanged here.

---

## 7. Local-language voice output

Meta's MMS-TTS (a VITS-family model, ONNX-exportable, covering 1,100+ languages including Hindi and Punjabi) is the practical choice here — small enough to run without heavy infrastructure, and already available pre-converted to ONNX in several community repositories.

### Two things to know before you commit to this

**Licensing:** MMS-TTS ships under CC-BY-NC-4.0 — non-commercial use only. Fine for this Challenge; flag it explicitly if this project is ever pitched toward real commercial or government procurement, where a commercially licensed TTS model would need to replace it.

**Quantization is finicky:** naive INT8 quantization of the VITS architecture's HiFi-GAN vocoder stage has documented failure modes — it can produce noise instead of speech. Run the fp32 or a carefully validated fp16 export, verify output by ear, and don't assume INT8 "just works" the way it does for the vision or LLM models. Given the model's small footprint (roughly 100–150MB per language), CPU inference is a perfectly reasonable choice here — this isn't the piece of the pipeline that needs to prove NPU usage.

---

## 8. Probe firmware & protocol

- Poll all four sensors on a fixed interval (e.g. every 2 seconds); never let a slow sensor read block the others — poll them independently or with a hard per-sensor timeout.
- Own the LED/buzzer directly from the probe's own controller, so a physical alert can fire even if the USB link to the field unit is cut — this is the dead-man's-switch layer.
- Frame telemetry as newline-terminated JSON with a simple checksum; on a checksum failure, resend rather than pass a malformed frame upstream.
- If a sensor's readings go stale or flatline in a way that suggests hardware failure rather than a real stable reading, mark that sensor's status as faulty — never let a dead sensor look identical to a "still and safe" one.

---

## 9. Field unit & city dashboard

| Piece | Choice | Reasoning |
|---|---|---|
| Backend | FastAPI + Uvicorn | WebSocket support for pushing live readings without polling |
| Field-unit view | Large GO/NO-GO banner, live readings, guidance text + audio playback, site notes | The one screen a supervisor actually uses in the field — keep it calm and unambiguous, not dense |
| City-layer view | A simple map of monitored sites, colored by latest risk tier, with a history log per site | Feeds directly into ERSU dispatch and NAMASTE reporting conversations |
| State store | Local SQLite for site history; no cloud database | Keeps sensitive municipal infrastructure data on-device, matching the data-sovereignty argument in the roadmap doc |
| Sync (optional, don't over-build) | A simple "pending sync" counter incremented on every inspection saved while offline, cleared on the next successful connection to the city layer | Enough to demonstrate "safety never waits for a network," which is the actual point — a full sync protocol is not necessary to make this claim credibly in a demo |

---

## 10. Packaging internals

Unchanged in substance from the earlier companion spec: keep Genie context binaries and TTS model files out of Git history (GitHub Releases as the preferred host), use a PyInstaller spec with the QNN native DLLs explicitly listed as binaries, and build via the free `windows-11-arm` GitHub Actions runner for a genuine native ARM64 executable without owning hardware full-time.

```yaml
name: build-windows-arm64
on: [push, workflow_dispatch]
jobs:
  build:
    runs-on: windows-11-arm
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt pyinstaller
      - run: python scripts/fetch_models.py
      - run: pyinstaller praan.spec
      - uses: actions/upload-artifact@v4
        with: { name: Praan-arm64, path: dist/ }
```

---

## 11. Testing & validation plan

| Layer | What to test | Needs hardware? |
|---|---|---|
| Rule engine (highest priority) | Every threshold boundary, every sensor-fault combination, multiple simultaneous violations — see §4 | No |
| Guidance pipeline | The LLM never contradicts the rule engine's decision across a battery of test decisions — this is worth automating as a regression check, not just eyeballing a few outputs | No (can test against the Genie bundle on any device that runs it) |
| Voice output | Manually verify pronunciation and clarity in each supported language — automated ASR-based verification is a nice-to-have, not required | No |
| Hardware-in-the-loop | Full pipeline with the real probe in a real or simulated wet, sulfide-heavy test environment | Yes |
| Fail-safe test | Physically disconnect one sensor mid-run and confirm the system immediately falls to NO-GO / unknown, never continues showing a stale "safe" | Yes |
| Offline test | Full loop with Wi-Fi disabled | Yes |

---

## 12. Benchmarking methodology

Use AI Hub's Job API to get CPU-vs-QNN latency numbers for the LLM without needing physical hardware, exactly as in the earlier companion spec's §12. For this project, add one more row that matters more than usual: **end-to-end latency from a sensor reading crossing a threshold to a spoken guidance message being audible** — for a life-safety alert, this number is arguably more important than any individual model's latency.

---

## 13. Failure modes & fallback logic

| Failure | Fallback behaviour |
|---|---|
| Any single sensor fails or disconnects | Immediate UNKNOWN — a distinct state from NO_GO, never averaged away, never rendered like a stable "safe" reading |
| Genie/LLM pipeline fails or times out | Dashboard still shows the raw rule-engine decision and violated thresholds in plain text — never a blank or stuck screen |
| TTS fails | Fall back to on-screen text in the target language; the decision itself is never gated on voice output succeeding |
| Field unit loses power or crashes | The probe's own LED/buzzer dead-man's-switch is still live and independent — this is the actual last line of defense |

---

## 14. Appendix: dependency pins

| Package | Pin to |
|---|---|
| python | 3.12.x, ARM64 build on-device |
| QAIRT SDK / Genie | ≥ 2.29.0 |
| qai_hub_models | latest at project start |
| onnxruntime (for TTS, CPU is acceptable) | latest stable |
| fastapi / uvicorn | latest stable |
| pyinstaller | ≥ 5.7.0 |
| scikit-learn or a gradient-boosting library | latest, for the predictive layer |
