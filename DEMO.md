# Praan System Demo Guide

This guide walks through a complete demonstration of the Praan safety system.

## Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Verify installation
python run.py test
```

## Demo Flow (3-Minute Version)

### 1. Introduction (0:00 - 0:20)

**Script**: "Before anyone enters a sewer or septic tank, Praan checks the air. This is a live safety system with a simulated probe. Watch how it detects hazards and gives clear guidance."

### 2. Safe Scenario (0:20 - 0:45)

```bash
# Start the backend
python run.py backend
```

Open browser to `http://localhost:8000/dashboard`

**Show:**
- ✅ Green "GO" banner
- All sensors showing safe readings
- Guidance: "वायु सुरक्षित है। प्रवेश की अनुमति है।"
- Provenance panel showing "deterministic_rule_engine" decided

**Say**: "All readings are safe. The rule engine - not AI - makes this decision. The AI only translates it to Hindi."

### 3. Live Hazard Detection (0:45 - 1:10)

Click **"H₂S Buildup"** scenario button

**Show:**
- Banner turning yellow (CAUTION), then red (NO-GO)
- H₂S sensor card turning red
- Live readings increasing
- Guidance changing: "अंदर मत जाइए। H₂S खतरनाक स्तर पर है।"

**Say**: "Watch the H₂S rise. The moment it crosses the threshold, the system immediately shows NO-GO. This is the Snapdragon AI moment - the guidance is generated on-device, entirely offline."

### 4. Offline Operation (1:10 - 1:30)

**Open DevTools (F12) → Network tab → Set to Offline**

Click **"Mixed Hazard"** scenario

**Show:**
- System still works
- Offline indicator appears
- "⚠️ OFFLINE MODE - All operations local" banner
- Decision still updates, guidance still generates

**Say**: "I just turned off the network. Everything still works. The decision, the AI explanation, everything runs locally on the Snapdragon device. This is critical - a worker's life can't depend on a network connection."

### 5. Sensor Fault Detection (1:30 - 1:50)

Click **"Sensor Fault"** scenario

**Show:**
- Banner turns gray: "UNKNOWN"
- One sensor card shows "FAULT" status
- Guidance: "सेंसर में खराबी है। प्रवेश न करें।"

**Say**: "This is NOT a safe reading. UNKNOWN means we can't verify the atmosphere. Notice it looks completely different from GO - this prevents a broken sensor from giving false confidence."

### 6. Decision Provenance (1:50 - 2:10)

Point to **Provenance panel**

**Show:**
- Decision Source: deterministic_rule_engine
- Explanation Source: on_device_llm
- Sensors Operational: 4/4 (or 3/4 in fault scenario)

**Say**: "The AI never decided whether it's safe. Look at this provenance panel - it clearly shows the deterministic rule engine made the call. The LLM only translated it. This is auditable, transparent, and safe."

### 7. City Layer (2:10 - 2:30)

Navigate to `http://localhost:8000/city`

**Show:**
- Aggregated site statistics
- Inspection history
- Hazard counts per site

**Say**: "This is the municipal view. Every inspection is logged. Supervisors can see which manholes are chronically dangerous, which need priority attention, and feed this directly into emergency response planning."

### 8. Close (2:30 - 3:00)

**Script**: "Praan solves one specific problem: is it safe to enter, right now, at this exact opening. It does this offline, in local languages, with the AI explaining decisions it never made. This is what on-device AI should look like for life-safety applications."

## Extended Demo (10-Minute Version)

### Additional Points to Cover

1. **Testing Rigor**
   ```bash
   python run.py test
   ```
   Show 90 passing tests, explain boundary testing

2. **Hardware Integration Plan**
   - Show `firmware/README.md`
   - Explain Arduino probe design
   - Show dead-man's-switch concept

3. **Technical Architecture**
   - Open `docs/technical_architecture.md`
   - Show the rule/LLM split diagram
   - Explain why this matters for certification

4. **Government Alignment**
   - Open `docs/project_overview.md`
   - Show NAMASTE scheme alignment
   - Explain pilot-to-procurement path

5. **NPU Usage** (when Genie integrated)
   - Show NPU visibility panel
   - Benchmark CPU vs NPU latency
   - Task Manager showing Hexagon usage

## Demo Hardware Setup

### If You Have Real Sensors

1. Wire 4 sensors to Arduino
2. Flash `firmware/probe_node.ino`
3. Update `backend/app.py` to use serial connection
4. Show physical probe being lowered

### Without Real Sensors

- Use simulated probe (current implementation)
- Explain this is for demo; hardware pending
- Show simulation provides realistic data patterns

## Common Demo Questions & Answers

**Q: Is the AI making the safety decision?**
A: No. The deterministic rule engine decides. The AI only explains it in plain language. See the provenance panel.

**Q: What if the network goes down?**
A: Everything works offline - that's why we built it on Snapdragon. Try it - I'll turn off WiFi right now.

**Q: How do you know the thresholds are correct?**
A: They come from OSHA and NIOSH published standards. See `safety/thresholds.py` - every number is cited.

**Q: What about false positives?**
A: We'd rather a false NO-GO than a false GO. The CAUTION state exists for borderline readings - it tells supervisors to re-test, not hard-stop.

**Q: Can this work in [other language]?**
A: The architecture supports it. We're using Hindi now. The LLM and TTS pipeline can handle 1000+ languages when fully integrated.

**Q: What's the path to real deployment?**
A: Pilot with one city's ERSU team → cross-validate against certified meters → inclusion in NAMASTE equipment standards. See section 8 of project_overview.md.

## Post-Demo Follow-Up

Provide attendees with:
- GitHub repository link
- `README.md` (quick start guide)
- `docs/project_overview.md` (full system description)
- Contact information for pilot collaboration

## Demo Checklist

Before presenting:
- [ ] Backend starts without errors
- [ ] Dashboard loads in browser
- [ ] All 5 scenarios switch correctly
- [ ] Offline mode works (test with DevTools)
- [ ] Tests pass (run `python run.py test`)
- [ ] You can explain the provenance panel clearly
- [ ] You can answer "does the AI decide safety?" correctly

## Recording Tips

If recording video:
1. Use 1920x1080 resolution
2. Zoom browser to 125% for visibility
3. Narrate what you're clicking
4. Show the offline demo - it's the most powerful moment
5. Keep it under 3 minutes for maximum impact
