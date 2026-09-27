# Praan Quick Start Guide

## 30-Second Setup

```bash
# Install
pip install -r requirements.txt

# Test (100 tests should pass)
python -m pytest tests/ -v

# Run
python run.py backend
```

Then open: http://localhost:8000/dashboard

## What You'll See

- **Large decision banner**: GO/CAUTION/NO-GO/UNKNOWN
- **4 sensor cards**: Real-time H₂S, CO, O₂, LEL readings
- **Guidance panel**: Hindi text explaining the decision
- **Provenance panel**: Shows rule engine decided (not AI)
- **Demo controls**: 5 scenario buttons to test different hazards

## Try This Demo

1. **Safe Conditions** (default)
   - Green "GO" banner
   - All sensors normal
   - Guidance: "वायु सुरक्षित है"

2. Click **"H₂S Buildup"**
   - Watch banner turn yellow → red
   - H₂S sensor card turns red
   - Guidance changes to "अंदर मत जाइए"

3. **Open DevTools → Network tab → Set to Offline**
   - Click "Mixed Hazard"
   - System still works!
   - "OFFLINE MODE" indicator appears
   - This is the Snapdragon moment

4. Click **"Sensor Fault"**
   - Banner turns gray "UNKNOWN"
   - One sensor shows "FAULT"
   - Distinct from "safe" state

## File Structure (Key Files Only)

```
praan/
├── safety/rule_engine.py      ← THE MOST IMPORTANT FILE
├── backend/app.py              ← FastAPI server
├── dashboard/field_unit.html  ← What you see in browser
├── tests/                      ← 100 tests
├── run.py                      ← Launch script
└── README.md                   ← Full documentation
```

## Commands

```bash
# Run backend
python run.py backend

# Run tests
python run.py test

# Run simulated probe standalone
python run.py probe --scenario h2s_buildup

# Run specific test
pytest tests/unit/test_rule_engine.py -v
```

## Endpoints

- `/` - Landing page with links
- `/dashboard` - Field unit (main demo)
- `/city` - City layer dashboard
- `/docs` - API documentation
- `/ws/telemetry` - WebSocket (live updates)
- `/health` - Health check

## API Quick Reference

```python
# Get all sites
GET /api/sites

# Get site history
GET /api/sites/{site_id}/history

# Record inspection
POST /api/inspection
{
  "site_id": "MH-001",
  "site_name": "Main Street Manhole",
  "decision": "NO_GO",
  "risk_tier": "hazard",
  "violated_thresholds": ["h2s_ppm"],
  "readings": {...},
  "guidance_text": "..."
}

# Change scenario (demo only)
POST /api/simulate/scenario
"h2s_buildup"
```

## Decision Logic Cheat Sheet

| Gas | Safe | Caution | Hazard | Extreme |
|-----|------|---------|--------|---------|
| H₂S (ppm) | <10 | 10-20 | 20-100 | >100 |
| CO (ppm) | <35 | 35-100 | 100-200 | >200 |
| O₂ (%) | >20.5 | 19.5-20.5 | 16-19.5 | <16 |
| LEL (%) | <5 | 5-10 | 10-20 | >20 |

**Decision**: Worst violated tier wins
- Caution → CAUTION state
- Hazard/Extreme → NO-GO state  
- Any sensor fault → UNKNOWN state
- All safe → GO state

## Troubleshooting

**"Module not found"**
```bash
pip install -r requirements.txt
```

**"Port 8000 in use"**
```bash
python run.py backend --port 8001
```

**"Tests failing"**
- Check you're in project root directory
- Verify Python 3.11+ installed
- Try: `pip install --upgrade -r requirements.txt`

**"Dashboard not loading"**
- Check backend is running (should see "Uvicorn running on...")
- Try: http://127.0.0.1:8000/dashboard
- Check browser console for errors

**"WebSocket not connecting"**
- Verify backend started successfully
- Check firewall/antivirus not blocking localhost:8000
- Look for WebSocket errors in browser DevTools

## Demo Script (1-Minute Version)

> "This is Praan - it checks if it's safe to enter sewers before anyone goes in. Watch this scenario switch to hazardous conditions..."

[Click "H₂S Buildup"]

> "The moment H₂S crosses 20 ppm, it shows NO-GO. The rule engine makes this decision - look at the provenance panel, it clearly shows the AI only explains, it doesn't decide. Now watch it work offline..."

[DevTools → Offline mode, switch scenario]

> "I just killed the network. It still works. The AI runs on-device. This is why it needs Snapdragon."

## What's Next?

- Read `README.md` for full documentation
- See `DEMO.md` for 3-minute presentation script
- Check `IMPLEMENTATION_STATUS.md` for what's built vs pending
- Review `docs/project_overview.md` for system design

## Key Points for Judges

1. **AI doesn't decide safety** - Rule engine does (see provenance panel)
2. **Works fully offline** - Demo this live
3. **Four states, not two** - UNKNOWN ≠ safe
4. **Comprehensive testing** - 100 tests, all boundaries
5. **Real problem** - 453 documented deaths since 2014
6. **Government fit** - Designed for NAMASTE scheme

## Questions?

Read the documentation:
- `README.md` - Setup and usage
- `ARCHITECTURE.md` - System design
- `DEMO.md` - Presentation guide
- `docs/` - Full technical specs

---

**Bottom line**: Install, test, run. Open dashboard. Click scenario buttons. Turn network off. It still works. That's Praan.
