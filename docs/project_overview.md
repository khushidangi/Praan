# Praan: pre-entry safety intelligence for confined-space sanitation work

*Working title — rename freely. Praan (प्राण) means breath, or life-force: the thing this device exists to protect before someone climbs into a space where the air itself can kill them.*

---

## CONTENTS

1. [The problem, plainly](#1-the-problem-plainly)
2. [The solution](#2-the-solution)
3. [Architecture — three tiers](#3-architecture--three-tiers)
4. [Hardware shopping list](#4-hardware-shopping-list)
5. [Model & software stack](#5-model--software-stack)
6. [Why this has to be Snapdragon](#6-why-this-has-to-be-snapdragon)
7. [Why Snapdragon is the right deployment platform](#7-why-snapdragon-is-the-right-deployment-platform)
8. [The government collaboration path](#8-the-government-collaboration-path)
9. [Phase-by-phase roadmap](#9-phase-by-phase-roadmap)
10. [Scoring alignment](#10-scoring-alignment)
11. [Submission checklist](#11-submission-checklist)
12. [Risk register](#12-risk-register)
13. [The honest limits of this prototype](#13-the-honest-limits-of-this-prototype)

---

## 1. The problem, plainly

**This isn't a hypothetical use case. It's an ongoing, documented cause of death that a specific government program is actively trying to fix right now.**

The Ministry of Social Justice and Empowerment has confirmed at least 453 deaths during sewer and septic tank cleaning since 2014, reported to Parliament. The actual cause, almost every time, is the same: hydrogen sulfide, methane, carbon monoxide, or plain oxygen depletion inside a confined space — gases that are often invisible and give no warning before they kill.

Because workers are rarely issued real gas-detection equipment, informal and unscientific proxies have taken its place in practice — dropping a stone, watching whether insects or rodents flee the opening, lowering a flame to see if it extinguishes. None of these reliably detect the actual danger. This is the exact gap the government's own mechanization program was created to close.

The Prohibition of Employment as Manual Scavengers and their Rehabilitation Act, 2013 already bans manual entry into sewers and septic tanks without protective equipment. The NAMASTE scheme (National Action for Mechanised Sanitation Ecosystem — a joint program of the Ministry of Social Justice & Empowerment and the Ministry of Housing & Urban Affairs, operational since 2023–24) is the current national effort to eliminate hazardous manual entry entirely, through mechanization, worker profiling, PPE, and dedicated Emergency Response Sanitation Units (ERSUs) "equipped with specialised safety devices for sewer emergencies."

That last phrase is the opening this project builds toward: a named, funded government category with no dominant technology inside it yet.

---

## 2. The solution

### WORKING TITLE — RENAME FREELY

**Praan: a pre-entry hazard probe and decision-support unit for sewer and septic tank work**

Before anyone enters a manhole, tank, or drain, a tethered sensor probe is lowered in first and measures the air: hydrogen sulfide, carbon monoxide, oxygen level, and combustible gas concentration. A Snapdragon-powered field unit — carried by the site supervisor or an ERSU team, not by the worker going underground — reads those measurements, cross-checks them against the site's hazard history, and produces a clear GO / NO-GO decision, spoken aloud in the local language, entirely offline.

**No camera, anywhere in the system.** No one's face, movement, or identity is captured. The only thing being measured is whether the air in a specific enclosed space is safe to breathe — which is both the more implementable design and, for this specific problem, the more honest one.

This deliberately does not try to be a general safety platform. It solves one narrow, well-defined, life-or-death decision — *is it safe to go in, right now, at this exact opening* — and does that one thing as reliably as a hackathon-stage prototype reasonably can.

### The one-line pitch

> **Praan predicts where sanitation hazards are likely, verifies the air before entry, and gives supervisors an auditable GO/NO-GO decision with offline, local-language guidance — all on-device.**

That sentence is the whole product. Everything below either builds one of its four verbs or it doesn't belong in the first submission.

### Predict → Verify → Respond → Learn

This loop is the actual AI story, and it's the thing to lead with in any pitch — not the gas sensor, which is the least novel part of the system.

| Stage | Question it answers | What decides it |
|---|---|---|
| **Predict** | Where should we be careful before we even arrive? | The small predictive model, reading site history — never overrides a live sensor, only prioritizes attention |
| **Verify** | Is it safe to enter, right now? | The live probe + the deterministic rule engine — the only thing allowed to decide GO/NO-GO |
| **Respond** | What should the supervisor actually do? | The on-device LLM, translating a decision it did not make into plain, spoken instruction |
| **Learn** | What is this telling us across the whole city? | Every inspection logged back into site history, sharpening the next Predict stage |

This is also the answer to the obvious judge question — "where's the AI innovation, this is just a gas detector with a chatbot on it?" It isn't one model doing one job. It combines predictive ML, deterministic safety engineering, and generative AI, with each deliberately restricted to what it is actually good at, feeding a loop that gets smarter with every inspection.

---

## 3. Architecture — three tiers

| Tier | Hardware | Job |
|---|---|---|
| **The Probe** | Small, cable-tethered sensor pod on a simple microcontroller (STM32-class); battery-powered, rugged casing | Lowered into the manhole or tank before entry. Reads H₂S, CO, O₂, combustible gas (LEL), and temperature on a fixed loop. Carries its own local LED/buzzer as a dead-man's-switch alert independent of everything upstream. |
| **The Field Unit** | HP laptop, Snapdragon X — carried by the supervisor or ERSU team | Reads the probe's telemetry, runs the risk-fusion and predictive model, generates a plain-language GO/NO-GO decision through an on-device LLM, and speaks it aloud in the local language. This is where the NPU does its real work. |
| **The City Layer** | Same or a second Snapdragon PC, at the municipal engineering office | Aggregates readings across every monitored manhole into a hazard map — which locations are chronically dangerous, which need priority mechanization — feeding directly into ERSU dispatch and NAMASTE compliance reporting. |

**Data flows probe → field unit → (periodically) city layer.** Nothing needs to leave the device to produce the one decision that matters in the moment: *is it safe to go in.*

### The decision is four states, not two

A binary safe/unsafe is less honest than the sensors actually are. Use four:

- **GO** — verified within safe limits
- **CAUTION** — approaching a threshold or readings unstable; re-test before proceeding, don't treat as a hard stop
- **NO-GO** — a defined hazardous condition exists
- **UNKNOWN** — a sensor fault or dropped connection means the atmosphere cannot be verified at all, and this must never visually resemble a stable "safe" reading — *no data is not the same as safe data*

### Decision provenance — make the AI/rules split visible, not just true

Every decision the app shows should have a small, expandable "why" that states plainly: *decision generated by the deterministic safety rule engine; explanation generated by on-device Snapdragon AI; sensor status 4/4 operational.* This costs almost nothing to build and is the single clearest way to show a judge that the LLM never got to invent the safety call — it only explains a decision that already existed.

### Make the NPU visible, not just claimed

Put a small, plain panel in the app itself — not just the README — showing: which model is running, that it's on the Hexagon NPU via Genie/QNN, that the network connection is off, and the actual measured latency (ideally CPU-vs-NPU side by side, using only real numbers from your own benchmarking). A judge watching that panel update live is a fundamentally stronger technical claim than the same number sitting in a markdown table they may never open.

---

## 4. Hardware shopping list

| Part | Purpose | Approx. price |
|---|---|---|
| Arduino UNO Q or a plain STM32 dev board | Probe controller | ₹2,500–7,500 |
| H₂S gas sensor module (e.g. electrochemical type) | Primary toxic-gas detection | ₹800–1,500 |
| CO gas sensor module | Secondary toxic-gas detection | ₹500–1,000 |
| O₂ sensor module | Oxygen depletion detection — arguably the single most important reading | ₹1,200–2,500 |
| Combustible gas / LEL sensor (e.g. methane-sensitive) | Explosive-atmosphere detection | ₹600–1,200 |
| Weatherproof, corrosion-resistant probe housing + tether cable (5–8m) | Survives the actual environment it's lowered into | ₹1,000–2,000 |
| LED + buzzer | Local, standalone dead-man's-switch alert on the probe itself | ₹150–300 |
| Small portable speaker (if the field unit's built-in speaker isn't loud enough for outdoor use) | Audible voice guidance on-site | ₹500–1,000 |

**Total add-on spend: roughly ₹6,500–13,500.** Every sensor here is a mature, off-the-shelf confined-space-entry component — this is intentionally not novel hardware, because novel hardware is exactly what you don't want on a life-safety device.

---

## 5. Model & software stack

| Task | Approach | Runs on |
|---|---|---|
| Gas threshold evaluation | Deterministic rule engine against published occupational exposure limits (OSHA/NIOSH reference thresholds for H₂S, CO, O₂, LEL) — not a model. The decision-maker must be auditable. | Field unit, plain Python, negligible compute |
| Pre-entry risk prediction | A small tabular model (gradient-boosted trees or logistic regression) trained on available site-history data — season, time since last cleaning, past incidents at that location — to flag likely-hazardous sites before the probe even goes down. If real municipal incident data is unavailable for the prototype, the model will use clearly documented synthetic or scenario-based data rather than implying validated real-world predictive accuracy. | Field unit / Hexagon NPU (a model this small will also run fine on CPU; NPU is a nice-to-have here, not the headline claim) |
| Plain-language, spoken GO/NO-GO guidance | A small instruct LLM (e.g. Llama-3.2-3B-Instruct) via Qualcomm's Genie runtime, translating the rule engine's decision and readings into a short, clear instruction | Field unit, Hexagon NPU via QNN — this is the headline NPU claim |
| Local-language voice output | Meta's MMS-TTS (VITS-based, ONNX-exportable, covers Hindi, Punjabi, and 1,100+ other languages) — note its license is non-commercial (CC-BY-NC-4.0), which is fine for a hackathon prototype but worth flagging if this ever goes commercial | Field unit — CPU is likely fine given the model's small size; attempt QNN, but don't force it if INT8 quantization of the VITS vocoder proves unstable |
| City hazard dashboard | FastAPI backend, simple map view aggregating site history | City-layer PC, CPU |

### The one design rule that matters most here

**The LLM never decides whether it's safe.** It only explains, in plain language and the right voice, a decision the deterministic rule engine already made from the raw sensor thresholds. If the LLM pipeline fails for any reason, the system still shows the raw GO/NO-GO from the rule engine — never a blank screen, and never a generative model in the safety-critical decision path.

---

## 6. Why this has to be Snapdragon

- **Offline is a hard requirement, not a preference.** A decision about whether a human enters a space that can kill them in minutes cannot depend on a network call succeeding. Many of the actual sites — older city sewer networks, informal settlements — have unreliable or no connectivity.
- **Battery life matches the actual job.** ERSU teams move manhole to manhole all day with no desk and no guaranteed charging point. A multi-day-battery Snapdragon device is a real, provable fit, not a marketing line.
- **Data sovereignty.** A citywide map of which manholes are chronically toxic is sensitive municipal infrastructure data. On-device processing means it never has to leave a government-controlled device to be useful in the moment.
- **The NPU is what makes voice guidance in a worker's own language possible in real time, offline** — a cloud LLM call for a life-safety instruction introduces exactly the kind of latency and reliability risk this application can't tolerate.

---

## 7. Why Snapdragon is the right deployment platform

The project is designed around a deployment environment where connectivity cannot be assumed and where the safety-critical decision must remain local.

- **Offline is a hard requirement, not a preference.** A decision about whether a human enters a space that can kill them in minutes cannot depend on a network call succeeding. Many of the actual sites — older city sewer networks, informal settlements — have unreliable or no connectivity.
- **Battery life matches the actual job.** ERSU teams move manhole to manhole all day with no desk and no guaranteed charging point. A multi-day-battery Snapdragon device is a real, provable fit, not a marketing line.
- **Data sovereignty.** A citywide map of which manholes are chronically toxic is sensitive municipal infrastructure data. On-device processing means it never has to leave a government-controlled device to be useful in the moment.
- **The NPU enables practical local AI.** The LLM guidance layer can run through Qualcomm's Genie/QNN stack on the Hexagon NPU, allowing short local-language instructions to be generated without sending sensor readings or site information to a cloud service.
- **The architecture makes the hardware contribution measurable.** Rather than simply claiming that Snapdragon is faster, the submission will benchmark the actual guidance pipeline and expose CPU-vs-NPU latency and offline operation directly in the application.

> The important distinction is that Snapdragon is not being used to replace the deterministic safety layer. The safety decision remains lightweight, local, and auditable. Snapdragon's AI acceleration is used where on-device intelligence adds value: predictive prioritization and natural-language guidance.

---

## 8. The government collaboration path

| Entity | Role |
|---|---|
| **NAMASTE scheme** | The active national program (2023–24 onward) this device is built to plug into — it already funds PPE, mechanized equipment, and ERSU safety devices, and has published standardized procurement rates for equipment as of its 2026 rollout. |
| **NSKFDC** (National Safai Karamcharis Finance and Development Corporation) | NAMASTE's implementing agency — the realistic point of contact for a pilot proposal. |
| **Ministries of Social Justice & Empowerment and Housing & Urban Affairs** | Joint scheme owners; policy and budget authority. |
| **Urban Local Bodies (ULBs) / municipal corporations** | The actual deployment sites — start with one or two, ideally ones already participating in the Smart Cities Mission, as a pilot before any national conversation. |

The realistic sequence: build and demo the working probe + field unit for this Challenge → pilot with a single willing ULB's ERSU team → use pilot data to make the case for inclusion in NAMASTE's standardized equipment list. Each step is small and concrete; none of it requires a new law or a new ministry to say yes to a brand-new idea.

---

## 9. Phase-by-phase roadmap

*Calibrated to roughly a four-week runway; compress or stretch proportionally against your actual deadline.*

### Build this, not that

Every one of the ideas below is individually good. Building all of them is how a strong, narrow project turns into a weak, sprawling one. This is the actual triage.

| Build this (core, do first) | Cut this (real, but not for v1) |
|---|---|
| Four-state decision (GO/CAUTION/NO-GO/UNKNOWN) | A calculated "probe reliability %" score — don't invent a number you can't defend |
| Decision provenance ("why" panel) | A full incident-replay screen with second-by-second telemetry |
| NPU visibility panel with real benchmark numbers | Site-to-site comparison analytics |
| Offline demo beat (Wi-Fi off, still works) | A fully built sync architecture — a "records pending sync: 3" counter is enough to tell the story |
| Physical dead-man's-switch demo (probe alarms independent of the laptop) | Separate, fully distinct "supervisor mode" vs "municipal mode" as two build tracks — one app with two screens is enough |
| Basic site history / "what this site has looked like" view | A rich site safety profile with trend graphs and multi-factor scoring |
| Predictive risk shown before the probe goes down | "What changed since last visit" diffing logic |

### The 3-minute demo script

Structure the live demo as a story, not a slide sequence.

**0:00 — Open with the problem**

> "Before anyone enters, Praan checks the air."

Open on a specific site with a known history: "This site has shown hazardous readings in 3 of its last 5 inspections."

**0:20** — Lower the probe. Live readings appear, resolve to GO. *(Predict / Verify)*

**0:45** — Introduce a hazard live (raise H₂S via the manual override). The screen flips to NO-GO, and the spoken guidance plays. *(Respond)*

**1:10** — Turn Wi-Fi off in front of the judges. Trigger the same NO-GO again. It still works, still speaks. *This is the Snapdragon moment — say so out loud.*

**1:30** — Open the decision provenance panel: rule engine decided, on-device AI explained, 4/4 sensors operational.

**1:50** — Cut power to the field unit entirely. The probe's own buzzer/LED keeps alarming. This is the moment that proves the system doesn't have a single point of failure.

**2:10** — Switch to the municipal view: this site now shows its fourth NO-GO this month, with a plain recommended action.

**2:30** — Close on the NPU panel: real CPU-vs-NPU latency numbers, "data sent to cloud: none." End there — don't add a summary slide after it.

---

### DAYS 1–4 · PHASE 0

**Setup and grounding**

- Create the GitHub repo, license, README skeleton.
- Register for Qualcomm AI Hub; confirm the Genie SDK (QAIRT ≥2.29.0) setup path.
- Order gas sensors and the probe housing — longest lead time, start first.
- Write down the exact occupational exposure thresholds you'll use for H₂S, CO, O₂, and LEL from a published reference standard (OSHA/NIOSH) — this becomes the rule engine's source of truth.

**Deliverable:** repo scaffolded, hardware ordered, thresholds documented with citations.

### DAYS 5–12 · PHASE 1

**Build the probe and the rule engine**

- Wire the four sensors to the microcontroller; write firmware that polls on a fixed interval and outputs a JSON telemetry frame.
- Build the standalone LED/buzzer dead-man's-switch alert directly on the probe, independent of the field unit.
- Write the deterministic rule engine (plain Python, unit-tested) that turns raw readings into a GO/NO-GO decision. This piece should be finished and correct before any model work starts.

**Deliverable:** a probe that reads real gas concentrations and a rule engine that a judge could read top to bottom and verify by hand.

### DAYS 10–18 · PHASE 2 (overlaps Phase 1)

**The LLM and voice pipeline, on real or borrowed hardware**

- Export a 3B-class instruct LLM through qai_hub_models for the Genie runtime; assemble the Genie bundle (tokenizer, config).
- Write the prompt template: rule-engine decision + readings + site history in, one short spoken-style instruction out, in the target language.
- Get Meta's MMS-TTS running (ONNX) for at least Hindi and one additional regional language; confirm CPU inference is fast enough before spending time chasing NPU quantization for it.
- Get a Task Manager screenshot showing the LLM's NPU usage during decode — your Technical Implementation evidence.

**Deliverable:** a spoken guidance message, generated on-device, in a local language, from a real sensor reading.

### DAYS 16–24 · PHASE 3

**Field unit integration and the predictive layer**

- Build the field-unit dashboard: current reading, GO/NO-GO banner, spoken guidance playback, site history.
- Train the small tabular predictive model on whatever historical/synthetic site data you can assemble; be upfront in the README about how it was trained if real incident data wasn't available.
- Wire the probe's serial link into the field unit; test the full offline loop with Wi-Fi disabled.

**Deliverable:** a working end-to-end demo: probe reading → rule engine → LLM → spoken guidance → dashboard, fully offline.

### DAYS 22–28 · PHASE 4

**Packaging, documentation, submission**

- Package as a Windows ARM64 executable via the GitHub Actions `windows-11-arm` runner.
- Write the README to the official spec, with the benchmark table and an explicit, honest "path to certification" note (see §13).
- Film the demo somewhere real if at all possible — even a controlled test tank or a municipal training site is more credible than a desk.
- Final review against every submission requirement; submit once.

**Deliverable:** submitted repo, packaged executable, demo video, completed intake form.

---

## 10. Scoring alignment

| Criterion | Satisfied by |
|---|---|
| **Technical Implementation** | Real QNN/Genie execution for the LLM, benchmark numbers, a correctly separated deterministic-decision-vs-generative-explanation architecture |
| **Application Use Case & Innovation** | A documented, government-tracked cause of death, with no existing dominant AI solution in this specific niche |
| **Deployment & Accessibility** | Fully offline operation, spoken local-language output for low-literacy users, packaged executable |
| **Presentation & Documentation** | README with cited safety thresholds, benchmark table, and an honest limitations section |

---

## 11. Submission checklist

- [ ] Public GitHub repo, entirely open-source
- [ ] README: description, team names/emails, from-scratch setup, run instructions, cited gas-exposure thresholds
- [ ] Open-source license file
- [ ] Packaged `.exe` or `.msix`
- [ ] Fully offline operation, demonstrated with Wi-Fi disabled
- [ ] Benchmark table and architecture note in the README
- [ ] An explicit limitations / path-to-certification section — see §13
- [ ] One submission only, reviewed fully before sending

---

## 12. Risk register

**Sensor disagreement or a single sensor failing quietly**

A confident but wrong "safe" reading is the single worst failure mode this project can have.

*Fix:* never let one sensor's reading alone produce a GO. Require agreement across all four channels, and default to NO-GO or "unknown, do not enter" the instant any sensor reports out-of-range, disconnected, or drifting values.

**Corrosive, humid sewer environment degrades hardware quickly**

Consumer-grade electronics don't survive this environment for long.

*Fix:* budget real time for a sealed, corrosion-resistant housing; test the probe in a real or simulated wet, sulfide-heavy environment before the final demo, not just on a bench.

**Government adoption timelines are long**

Even a strong pilot doesn't turn into a national procurement line quickly.

*Fix:* keep the pitch scoped to what's realistic — a single-ULB pilot as the next step, not "this will be mandated nationwide." Judges will trust a modest, credible next step more than a grand claim.

---

## 13. The honest limits of this prototype

Say this plainly in the README, not just here: **this is a decision-support prototype built on commodity gas sensors, not a certified life-safety instrument.** Certified confined-space gas detectors (the kind used industrially — Dräger, MSA, BW Technologies units) go through calibration and regulatory validation this project has not undergone. The realistic claim is that this is a working proof of concept for an on-device, offline, voice-accessible early-warning layer — with a clear next step of cross-validating readings against a certified reference meter before any real deployment recommendation. A judge with safety-engineering background will trust the whole submission more for saying this directly than for implying otherwise.

---

*Sources: Challenge official rules, NAMASTE scheme documentation, OSHA/NIOSH occupational exposure limits.*
