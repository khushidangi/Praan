# Worker App Redesign - SURAKSHA SEVA

## Overview

The worker app has been completely rebuilt to match the "SURAKSHA SEVA" design system shown in the reference images. This is a mobile-first safety interface for sewer workers in India.

## Design System

### Brand Identity
- **Name**: सुरक्षा सेवा (SURAKSHA SEVA)
- **Tagline**: स्वच्छता एवं सुरक्षा प्रबंधन
- **Colors**: 
  - Background: `#F7F4EE` (warm paper)
  - Primary text: `#1F2933` (dark slate)
  - Secondary text: `#6B7280` (gray)
  - State colors: GREEN (`#1E8E4E`), RED (`#C62828`), BLUE (`#2F4B9A`), ORANGE (`#D97706`)

### Typography
- Supports Devanagari script (Hindi/Marathi)
- Supports Gurmukhi script (Punjabi)
- System fonts: `-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans Devanagari'`

## Screens Implemented

### 1. Join Screen
**Features:**
- App header with shield icon and "Ward 42 • Live" badge
- Multilingual interface (Punjabi, Hindi, English)
- Worker name input with icon
- Marshal information card showing: राजेश कुमार, मैनहोल व सीवर सफ़ाई यूनिट #08
- Location policy consent with three bullet points
- Privacy badge: "निजी डेटा पूर्णतः सुरक्षित एवं एन्क्रिप्टेड है"
- "मैं तैयार हूँ / I'm ready" button
- Server connection note

### 2. GO State (Safe to Enter)
**Features:**
- Green background (`#1E8E4E`)
- Header: "LIVE SIGNAL • सीधा संकेत" + "ZONE-4B"
- Large circular icon with checkmark
- Primary text: "आप अंदर जा सकते हैं।"
- Secondary text: "हवा 4:12 पहले जाँची गई थी।"
- English translation: "You may enter. Air was tested 4:12 ago."
- Real-time gas readings:
  - O₂ OXYGEN: 20.9%
  - H₂S TOXIN: 0.0 PPM
  - CO CARBON: 0 PPM
- Countdown timer: 25:46 with validity text
- "I'm entering / मैं अंदर जा रहा हूँ" button
- Supervisor permit badge: "SUPERVISOR PERMIT #4829 ACTIVE"
- Footer: Connection status + "Live Telemetry"

### 3. EVACUATE State (Emergency)
**Features:**
- Red background (`#C62828`)
- Flashing animation
- "EMERGENCY OVERRIDE" badge
- Header shows: "CH4 > 2.5%" (hazard info)
- Large evacuation icon (arrow up-right)
- Primary text: "अभी बाहर निकलें।"
- Secondary text: "EVACUATE NOW"
- Emergency warning card:
  - "If you are outside: nobody goes in. Do not enter to help. Call for help."
  - Hindi translation: "बाहर रहने वालों के लिए: कोई भी अंदर न जाए। मदद के लिए तुरंत कॉल करें।"
- "I'm out / मैं बाहर हूँ" button
- "SOS: Call Emergency Team (112)" button (calls tel:112)

### 4. HOLD State (Wait)
**Features:**
- Blue background (`#2F4B9A`)
- Header: "SAFETY HOLD ACTIVE" + "SITE #402-A"
- Hand icon (stop gesture)
- Primary text: "सुपरवाइजर ने अंदर जाने से मना किया है। अगले निर्देश का इंतज़ार करें।"
- English: "The supervisor has asked you not to enter. Wait for instructions."
- Field note card:
  - Header: "FIELD NOTE / संदेश"
  - Message: "Note from supervisor: Wait at the truck."
  - Hindi: "सुपरवाइजर का संदेश: ट्रक के पास इंतज़ार करें।"
  - Metadata: "Sent by Ramesh K. (Safety Marshal)" + "2 min ago"
- Listening status: "🎧 Listening for gate clearance..."

### 5. BLOCKED State (Unsafe)
**Features:**
- Red background (`#C62828`)
- Stop sign icon
- Primary text: "अंदर मत जाओ। हवा सुरक्षित नहीं है।"
- English: "DO NOT ENTER. The air is not safe."

### 6. NO SIGNAL State
**Features:**
- Displays when connection is lost for >6 seconds
- Primary text: "संपर्क टूट गया है"
- English: "No signal. Do not enter. If you are inside, leave now."

## Technical Implementation

### Files Modified
1. `web/worker/index.html` - Complete UI rebuild
2. `web/worker/worker.js` - State rendering logic updated

### Key Features
- **Responsive Design**: Mobile-first, max-width 440px
- **Multilingual**: Full Hindi, Punjabi, English support
- **Accessibility**: Large touch targets (pill buttons 28px radius)
- **Real-time**: WebSocket updates with 6-second watchdog
- **Safety**: Siren + vibration on EVACUATE
- **Wake Lock**: Keeps screen on during active session
- **Location Tracking**: Optional, session-only GPS
- **Offline-first**: Relative URLs, no CDN dependencies

### State Machine
```
HOLD → waiting for clearance
GO/READY → safe to enter
BLOCKED → unsafe, do not enter
EVACUATE → emergency exit now
NO_SIGNAL → connection lost
```

### WebSocket Protocol
**Client sends:**
- `hello`: Join with name, language, consent
- `loc`: GPS coordinates (if permitted)
- `ack`: "entering" or "exited" acknowledgments
- `hb`: Heartbeat every 5 seconds

**Server sends:**
- `state`: Current safety state + readings + text
- `hb`: Heartbeat response

## Design Compliance

✅ Matches all 4 reference images exactly:
1. Join screen with language selection
2. GO state with gas readings and timer
3. EVACUATE state with emergency warning
4. HOLD state with field note

✅ Design system compliance:
- Warm paper background (#F7F4EE)
- State colors only for meaning
- Pill buttons (28px radius)
- No gradients, no shadows
- No emoji in production UI (only for icons)
- Bilingual text (primary language large, English small)

## Testing

**To test the worker app:**

1. Start the backend:
   ```bash
   python run.py backend
   ```

2. Create a session via API:
   ```bash
   curl -X POST http://localhost:8000/api/sessions \
     -H "Content-Type: application/json" \
     -d '{"site_id": "402-A", "site_name": "Ward 42 Manhole", "supervisor_name": "Ramesh Kumar"}'
   ```

3. Open the worker join URL from the response:
   ```
   http://localhost:8000/w?session={session_id}&token={token}
   ```

4. Select language, enter name, click "मैं तैयार हूँ / I'm ready"

5. The app will connect via WebSocket and display the current session state

## Next Steps

To complete the full workflow:

1. **Backend Integration**
   - Hook up real session state machine
   - Connect to probe readings
   - Implement supervisor actions (hold, authorize, evacuate)

2. **Missing Features**
   - Voice synthesis for guidance (currently placeholder)
   - Real gas sensor readings (currently simulated)
   - Permit system with QR codes
   - Session history and sign-off

3. **Testing**
   - Test on actual mobile devices (Android, iOS)
   - Test with Hindi voice synthesis
   - Test offline mode (Wi-Fi off)
   - Test wake lock across browsers

## Files
- `web/worker/index.html` - UI markup and styles
- `web/worker/worker.js` - WebSocket client and state logic
- `backend/ws_worker.py` - Server-side WebSocket handler
- `session/manager.py` - Session state machine

## Notes

The design now exactly matches the "SURAKSHA SEVA" reference images. All text is bilingual (Hindi primary, English secondary), all visual elements match (colors, icons, layout), and the UX flow follows the Indian government service design patterns.
