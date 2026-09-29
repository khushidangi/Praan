# Praan Implementation Status

## Phase 0: Truth and Hygiene ✅ COMPLETE

### Fixed Defects
- ✅ D1: POST /api/simulate/scenario now uses Pydantic body model (422 error fixed)
- ✅ D2: Field UI saves inspections to city layer via /api/inspection
- ✅ D3: No false NPU claims - /api/ai/status shows real status
- ✅ D4: Audio button is placeholder (no alert())
- ✅ D5: Relative URLs for WebSocket and API calls (works with any port/protocol)
- ✅ D6: resource_path() helper for PyInstaller compatibility
- ✅ D7: Single probe reader broadcasts to all clients
- ✅ D8: DEMO.md updated - no false claims about NPU
- ✅ D9: Will be addressed in Phase 1 (limits.yaml)
- ✅ D10: Minimal docs (this file + README)

## Phase 1: Safety Core v2 ✅ COMPLETE

### Implemented
- ✅ safety/limits.yaml with TODO(HUMAN) placeholders for citations
- ✅ safety/config.py - YAML loader with citation validation
- ✅ safety/engine_v2.py - Enhanced rule engine with:
  - R-S1: Freshness checking, physical range validation, sensor status
  - R-S2: Limit violations with margin calculation
  - R-S3: Warn margin, rate of rise detection (least-squares trend), stabilization
  - R-S4: Consecutive GO readings required (hysteresis)
  - R-S5: Recovery band after NO_GO/UNKNOWN
  - R-S6: Pure function (deterministic, no I/O or randomness)
- ✅ /api/ai/status endpoint - shows real engine/provider status
  - Shows "template" mode (not claiming NPU)
  - Shows missing citations
  - Reports offline status and 0 cloud requests

### Not Yet Implemented
- ⏳ T1.3: Generate firmware/limits.h from YAML (Phase 8 - probe hardware)

## Phase 2: Sessions and Realtime ✅ COMPLETE

### Implemented
- ✅ session/manager.py - Complete state machine per Section 5:
  - All 9 states: PREP, SAMPLING, BLOCKED, READY, AUTHORIZED, IN_ENTRY, EVACUATE, CLOSING, CLOSED
  - R-N1: SessionManager is sole owner of worker-facing state
  - R-N2: NO_GO/UNKNOWN before entry → BLOCKED → STOP to workers
  - R-N3: NO_GO/UNKNOWN during entry → EVACUATE
  - R-N4: CAUTION during entry → WARN
  - R-N5: Stable GO → READY (workers stay on HOLD)
  - R-N6: Supervisor hold prevents authorization
  - R-N7: GO expiry (30 min default)
  - R-N8: EVACUATE latches until all clear
  - R-N9: Event logging with cause and actor
  - R-N10: Token-based auth, role separation
- ✅ session/events.py - Append-only event log
- ✅ session/auth.py - HMAC token authentication
- ✅ backend/ws_worker.py - Worker WebSocket handler
- ✅ Session API endpoints:
  - POST /api/sessions - Create session
  - POST /api/sessions/{id}/deploy_probe
  - POST /api/sessions/{id}/hold
  - POST /api/sessions/{id}/release_hold
  - POST /api/sessions/{id}/authorize
  - POST /api/sessions/{id}/evacuate
  - POST /api/sessions/{id}/all_clear
  - POST /api/sessions/{id}/close
  - GET /api/sessions/{id}
- ✅ Probe broadcast integrated with session manager

### Not Yet Implemented
- ⏳ T2.2: Full token validation and command rejection tests
- ⏳ T2.4: Sync queue for offline operation

## Phase 3: Worker App ✅ COMPLETE

### Implemented
- ✅ web/worker/index.html - Worker phone app with design system:
  - R-W1: Join flow with name, language, consent
  - R-W2: Full-screen states with glyph + text (large chosen lang, small English)
  - R-W3: Client-side 6-second watchdog → NO_SIGNAL
  - R-W4: Siren, vibration on EVACUATE
  - R-W5: Wake Lock request
  - R-W6: Location with consent (geolocation.watchPosition)
  - R-W7: Safety states shown regardless of location
  - R-W8: "I'm entering" only in GO, "I'm out" in GO/WARN/EVACUATE
  - R-W10: All resources loaded from hub (no external requests)
- ✅ web/worker/worker.js - WebSocket client:
  - Implements all worker → server messages (hello, loc, ack, hb)
  - Handles state updates with sequence numbers
  - Watchdog timer for NO_SIGNAL detection
  - Audio siren using Web Audio API
  - Vibration support
- ✅ Design system applied (warm paper #F7F4EE, state colors, pill buttons, no gradients)
- ✅ Canonical text in 3 languages (en, hi, pa) per Section 7.7
- ✅ /w endpoint serves worker app
- ✅ /s endpoint serves supervisor control interface

### Not Yet Implemented
- ⏳ R-W9: Timer rendering from server seconds (currently using client time)
- ⏳ R-W11: Task assignment cards
- ⏳ Rim mode (?mode=rim for spare display)
- ⏳ Recorded audio clips (currently using Web Audio siren)

## Phase 4: Supervisor and Ward UI - SUPERVISOR LIVE FLOW IMPLEMENTED

### Implemented
- ✅ web/supervisor/index.html - Connected supervisor flow:
  - Today site list and session creation
  - Worker join link with relative URL
  - Authenticated supervisor WebSocket with REST fallback
  - Live session state, simulated probe label, crew presence and entry status
  - Gas readings, limits, trends and reading age
  - Safety action plan and briefing checklist gate before authorization
  - Hold, release, deploy, authorize, evacuate, all-clear and sign-off controls
  - Append-only session timeline and provenance footer
- ✅ backend/app.py - Supervisor integration:
  - Supervisor token returned at session creation
  - `/ws/supervisor` streams authoritative session snapshots
  - `/api/sessions/{id}/snapshot` and `/timeline` REST fallbacks
- ✅ session/manager.py - Snapshot contract includes latest reading, decision, crew and timeline

### Not Yet Implemented
- ⏳ R-U1: Computed history scores and one-tap QR rendering
- ⏳ R-U3: Playbook-backed action assignment and completion effects
- ⏳ R-U7: Persisting a full session inspection record at wrap-up
- ⏳ Sparkline rendering and richer measured-effect telemetry
- ⏳ R-D1: Ward view per 7.10

## Phase 5: Playbook and Guidance - NOT STARTED
- ⏳ guidance/playbook.json
- ⏳ Canonical string set with needs_review flags
- ⏳ Validator
- ⏳ History score
- ⏳ Site brief

## Phase 6: Genie and NPU - NOT STARTED
- ⏳ Genie integration (human must export model first)
- ⏳ Real /api/ai/status reporting
- ⏳ Benchmarks

## Phase 7: Voice - NOT STARTED
- ⏳ Recorded audio clips
- ⏳ Browser TTS integration

## Phase 8: Probe Hardware - NOT STARTED
- ⏳ Serial probe ingest
- ⏳ Firmware
- ⏳ limits.h generation

## Phase 9: Ship - NOT STARTED
- ⏳ Certificate script
- ⏳ PyInstaller build
- ⏳ Fault injection tests
- ⏳ README
- ⏳ Demo video

## Current System Status

### What Works Now
1. ✅ Enhanced rule engine with oxygen upper bound, trend detection, hysteresis
2. ✅ Session state machine with all 9 states
3. ✅ Worker phone app (join, state display, watchdog, siren, location)
4. ✅ Supervisor interface (create session, control flow)
5. ✅ Worker WebSocket with token auth
6. ✅ Real-time state propagation (probe → engine → session → workers)
7. ✅ Event logging
8. ✅ AI status endpoint showing honest "template mode"

### Demo Flow
1. Open http://localhost:8000/ to see all interfaces
2. Open /s in browser (supervisor interface)
3. Create a session → Get worker join URL
4. Open worker URL on phone or second browser window
5. Worker joins with name and language
6. Supervisor clicks "Deploy Probe" → Session enters SAMPLING
7. Probe reads air → Engine decides → Session updates → Worker sees HOLD or STOP
8. If air is safe → Session enters READY
9. Supervisor clicks "Authorize Entry" → Worker sees GO
10. Worker taps "I'm entering" → Session enters IN_ENTRY
11. Change scenario to "h2s_buildup" → Air degrades → Worker sees WARN then EVACUATE
12. Worker taps "I'm out" → Supervisor clicks "All Clear"

### What's Missing for Competition
**Critical (40-point NPU criterion):**
- Phase 6: Real Genie/NPU integration with measured latency
- Benchmarks showing NPU vs CPU

**Important:**
- Phase 4: Full supervisor Live Site UI with action plan, timeline
- Phase 5: Playbook with canonical guidance
- Phase 9: ARM64 .exe build

**Nice to have:**
- Phase 7: Real audio clips
- Phase 8: Physical probe
- Full location implementation
- Task assignment

## Next Priority
1. **Human action**: Export Genie model on Snapdragon laptop (starts Phase 6)
2. **Kiro**: Complete Phase 4 supervisor UI (Live Site screen per 7.9)
3. **Kiro**: Implement Phase 5 playbook and canonical guidance
4. **Kiro**: Wire Genie when model is ready
5. **Kiro**: Benchmarks and /api/ai/status with real NPU data
