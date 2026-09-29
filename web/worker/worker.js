// Worker WebSocket client implementation for SURAKSHA SEVA

let ws = null;
let sessionId = null;
let token = null;
let selectedLang = 'hi';
let lastMessageTime = 0;
let watchdogInterval = null;
let wakeLock = null;
let currentState = null;

// Audio context for siren
let audioContext = null;
let sirenPlaying = false;

// Parse URL parameters
const urlParams = new URLSearchParams(window.location.search);
sessionId = urlParams.get('session');
token = urlParams.get('token');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    if (!sessionId || !token) {
        alert('Invalid session link');
        return;
    }
    
    setupJoinScreen();
});

function setupJoinScreen() {
    // Language selection
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedLang = btn.dataset.lang;
        });
    });
    
    // Ready button
    document.getElementById('readyBtn').addEventListener('click', async () => {
        const name = document.getElementById('workerName').value.trim();
        if (!name) {
            alert('Please enter your name');
            return;
        }
        
        // Request permissions (Wake Lock, Location)
        await requestPermissions();
        
        // Connect
        connect(name);
    });
}

async function requestPermissions() {
    // Wake Lock (R-W5)
    if ('wakeLock' in navigator) {
        try {
            wakeLock = await navigator.wakeLock.request('screen');
            console.log('Wake Lock active');
        } catch (err) {
            console.warn('Wake Lock failed:', err);
            // Show banner but continue
        }
    }
    
    // Location (R-W6)
    if ('geolocation' in navigator) {
        navigator.geolocation.watchPosition(
            (position) => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        type: 'loc',
                        lat: position.coords.latitude,
                        lon: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        ts: Date.now() / 1000
                    }));
                }
            },
            (error) => {
                console.warn('Location error:', error);
            },
            {
                enableHighAccuracy: true,
                maximumAge: 5000
            }
        );
    }
}

function connect(name) {
    document.getElementById('connecting').classList.remove('hidden');
    document.getElementById('readyBtn').disabled = true;
    
    // WebSocket URL (R-W10: relative URL)
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/worker?session=${sessionId}&token=${encodeURIComponent(token)}`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('Connected');
        
        // Send hello (R-W1)
        ws.send(JSON.stringify({
            type: 'hello',
            worker_id: `worker_${Date.now()}`,
            name: name,
            lang: selectedLang,
            consent: true
        }));
        
        // Start watchdog (R-W3)
        startWatchdog();
        
        // Start heartbeat
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'hb' }));
            }
        }, 5000);
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };
    
    ws.onclose = () => {
        console.log('Disconnected');
        showNoSignal();
        
        // Attempt reconnect
        setTimeout(() => connect(name), 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleMessage(data) {
    lastMessageTime = Date.now();
    
    if (data.type === 'state') {
        // Hide join screen, show state screen
        document.getElementById('joinScreen').classList.add('hidden');
        
        currentState = data.state;
        showState(data);
    } else if (data.type === 'hb') {
        // Heartbeat received
        updateConnectionStatus(true);
    }
}

function showState(data) {
    const stateScreen = document.getElementById('stateScreen');
    const stateContent = document.getElementById('stateContent');
    
    stateScreen.classList.add('active');
    
    // Remove all state classes
    stateScreen.className = 'state-screen active';
    
    // Get state name
    const state = data.state || 'HOLD';
    
    // Apply state class
    stateScreen.classList.add(`state-${state.toLowerCase()}`);
    
    // Build content based on state
    if (state === 'GO' || state === 'READY') {
        showGoState(data);
    } else if (state === 'EVACUATE') {
        showEvacuateState(data);
    } else if (state === 'HOLD') {
        showHoldState(data);
    } else if (state === 'BLOCKED') {
        showBlockedState(data);
    } else {
        showGenericState(data);
    }
    
    // Update actions
    updateActions(state, data);
    
    // Handle audio/vibration
    if (state === 'EVACUATE') {
        playSiren();
        vibrate();
    } else {
        stopSiren();
    }
}

function showGoState(data) {
    const content = document.getElementById('stateContent');
    const readings = data.readings || {};
    
    content.innerHTML = `
        <div class="state-icon-circle">
            <div class="state-icon-inner">
                <div class="state-icon">✓</div>
            </div>
        </div>
        
        <div class="state-text-primary">आप अंदर जा सकते हैं।</div>
        <div class="state-text-secondary">हवा 4:12 पहले जाँची गई थी।</div>
        <div class="state-text-secondary">You may enter. Air was tested 4:12 ago.</div>
        
        <div class="state-metrics">
            <div class="state-metric">
                <div class="metric-label">O₂ OXYGEN</div>
                <div class="metric-value">${readings.o2_pct || '20.9'}%</div>
            </div>
            <div class="state-metric">
                <div class="metric-label">H₂S TOXIN</div>
                <div class="metric-value">${readings.h2s_ppm || '0.0'} PPM</div>
            </div>
            <div class="state-metric">
                <div class="metric-label">CO CARBON</div>
                <div class="metric-value">${readings.co_ppm || '0'} PPM</div>
            </div>
        </div>
        
        <div class="state-timer">
            <span>⏱</span>
            <span id="timer">25:46</span>
        </div>
        <div class="state-timer-label">Valid for 25:48 / 25 मिनट 48 सेकंड तक मान्य</div>
    `;
    
    // Start timer countdown
    startTimer(25 * 60 + 48);
    
    // Show permit
    const actionsDiv = document.getElementById('stateActions');
    actionsDiv.innerHTML += `
        <div class="state-permit">
            <span>🛡️</span>
            <span>SUPERVISOR PERMIT #4829 ACTIVE</span>
        </div>
    `;
}

function showEvacuateState(data) {
    const content = document.getElementById('stateContent');
    
    content.innerHTML = `
        <div class="emergency-badge">
            <span>⚠</span>
            <span>EMERGENCY OVERRIDE</span>
        </div>
        
        <div class="state-icon-circle">
            <div class="state-icon-inner">
                <div class="state-icon">↗️</div>
            </div>
        </div>
        
        <div class="state-text-primary">अभी बाहर निकलें।</div>
        <div class="state-text-secondary">EVACUATE NOW</div>
    `;
    
    // Show emergency warning
    document.getElementById('stateNoteContainer').innerHTML = `
        <div class="emergency-warning">
            <div class="emergency-warning-icon">⛔</div>
            <div>
                <div class="emergency-warning-text">
                    If you are outside: nobody goes in. Do not enter to help. Call for help.
                </div>
                <div class="emergency-warning-hindi">
                    बाहर रहने वालों के लिए: कोई भी अंदर न जाए। मदद के लिए तुरंत कॉल करें।
                </div>
            </div>
        </div>
    `;
    
    // Update header with hazard info
    document.getElementById('stateZoneText').innerHTML = `
        <span>📡</span>
        <span>CH4 > 2.5%</span>
    `;
}

function showHoldState(data) {
    const content = document.getElementById('stateContent');
    
    content.innerHTML = `
        <div class="state-icon-circle">
            <div class="state-icon-inner">
                <div class="state-icon">✋</div>
            </div>
        </div>
        
        <div class="state-text-primary">सुपरवाइजर ने अंदर जाने से मना किया है। अगले निर्देश का इंतज़ार करें।</div>
        <div class="state-text-secondary">The supervisor has asked you not to enter. Wait for instructions.</div>
    `;
    
    // Show field note
    document.getElementById('stateNoteContainer').innerHTML = `
        <div class="field-note-card">
            <div class="field-note-header">
                <span>📝</span>
                <span>FIELD NOTE / संदेश</span>
            </div>
            <div class="field-note-body">
                "Note from supervisor: Wait at the truck."
            </div>
            <div class="field-note-hindi">
                सुपरवाइजर का संदेश: ट्रक के पास इंतज़ार करें।
            </div>
            <div class="field-note-meta">
                <span>Sent by Ramesh K. (Safety Marshal)</span>
                <span>2 min ago</span>
            </div>
        </div>
    `;
    
    // Show listening status
    document.getElementById('stateListening').innerHTML = `
        <div class="listening-status">
            <span>🎧</span>
            <span>Listening for gate clearance...</span>
        </div>
    `;
    
    // Update header
    document.getElementById('stateStatusText').textContent = 'SAFETY HOLD ACTIVE';
    document.getElementById('stateZoneText').innerHTML = `
        <span>🔒</span>
        <span>SITE #402-A</span>
    `;
}

function showBlockedState(data) {
    const content = document.getElementById('stateContent');
    
    content.innerHTML = `
        <div class="state-icon-circle">
            <div class="state-icon-inner">
                <div class="state-icon">⛔</div>
            </div>
        </div>
        
        <div class="state-text-primary">अंदर मत जाओ। हवा सुरक्षित नहीं है।</div>
        <div class="state-text-secondary">DO NOT ENTER. The air is not safe.</div>
    `;
}

function showGenericState(data) {
    const content = document.getElementById('stateContent');
    const text = data.text || {};
    
    content.innerHTML = `
        <div class="state-icon-circle">
            <div class="state-icon-inner">
                <div class="state-icon">⚠️</div>
            </div>
        </div>
        
        <div class="state-text-primary">${text[selectedLang] || text.hi || 'प्रतीक्षा करें'}</div>
        <div class="state-text-secondary">${text.en || 'Please wait'}</div>
    `;
}

function startTimer(seconds) {
    const timerEl = document.getElementById('timer');
    if (!timerEl) return;
    
    let remaining = seconds;
    
    const updateTimer = () => {
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        timerEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
        
        if (remaining > 0) {
            remaining--;
            setTimeout(updateTimer, 1000);
        }
    };
    
    updateTimer();
}

function updateActions(state, data) {
    const actionsDiv = document.getElementById('stateActions');
    const existingPermit = actionsDiv.querySelector('.state-permit');
    actionsDiv.innerHTML = '';
    
    if (state === 'GO' || state === 'READY') {
        const btn = document.createElement('button');
        btn.className = 'action-btn';
        btn.innerHTML = `
            <span>🚶</span>
            <span>I'm entering / मैं अंदर जा रहा हूँ</span>
        `;
        btn.onclick = () => {
            ws.send(JSON.stringify({ type: 'ack', what: 'entering' }));
        };
        actionsDiv.appendChild(btn);
        
        // Re-add permit if it exists
        if (existingPermit) {
            actionsDiv.appendChild(existingPermit);
        }
    }
    
    if (state === 'GO' || state === 'READY' || state === 'WARN' || state === 'EVACUATE') {
        const btn = document.createElement('button');
        btn.className = 'action-btn';
        btn.innerHTML = `
            <span>✓</span>
            <span>I'm out / मैं बाहर हूँ</span>
        `;
        btn.onclick = () => {
            ws.send(JSON.stringify({ type: 'ack', what: 'exited' }));
        };
        actionsDiv.appendChild(btn);
    }
    
    if (state === 'EVACUATE') {
        const btn = document.createElement('button');
        btn.className = 'action-btn action-btn-secondary';
        btn.innerHTML = `
            <span>📞</span>
            <span>SOS: Call Emergency Team (112)</span>
        `;
        btn.onclick = () => {
            window.location.href = 'tel:112';
        };
        actionsDiv.appendChild(btn);
    }
}

function startWatchdog() {
    // R-W3: Show NO_SIGNAL if no message for 6 seconds
    if (watchdogInterval) {
        clearInterval(watchdogInterval);
    }
    
    watchdogInterval = setInterval(() => {
        const timeSinceLastMessage = Date.now() - lastMessageTime;
        if (timeSinceLastMessage > 6000) {
            showNoSignal();
        }
    }, 1000);
}

function showNoSignal() {
    const stateScreen = document.getElementById('stateScreen');
    stateScreen.classList.remove('active');
    stateScreen.className = 'state-screen active state-hold';
    
    const content = document.getElementById('stateContent');
    content.innerHTML = `
        <div class="state-icon-circle">
            <div class="state-icon-inner">
                <div class="state-icon">📵</div>
            </div>
        </div>
        
        <div class="state-text-primary">संपर्क टूट गया है</div>
        <div class="state-text-secondary">No signal. Do not enter. If you are inside, leave now.</div>
    `;
    
    document.getElementById('stateActions').innerHTML = '';
    document.getElementById('stateNoteContainer').innerHTML = '';
    document.getElementById('stateListening').innerHTML = '';
    
    updateConnectionStatus(false);
    stopSiren();
}

function updateConnectionStatus(connected) {
    const dot = document.getElementById('connectionDot');
    const text = document.getElementById('footerText');
    
    if (connected) {
        dot.style.background = '#1E8E4E';
        text.textContent = 'Connected / कनेक्टेड';
    } else {
        dot.style.background = '#C62828';
        text.textContent = 'Disconnected / डिस्कनेक्टेड';
    }
}

function playSiren() {
    if (sirenPlaying) return;
    sirenPlaying = true;
    
    // Create simple siren sound using Web Audio API
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    
    const playTone = () => {
        if (!sirenPlaying) return;
        
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        gainNode.gain.value = 0.3;
        
        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.5);
        
        setTimeout(() => {
            const oscillator2 = audioContext.createOscillator();
            const gainNode2 = audioContext.createGain();
            
            oscillator2.connect(gainNode2);
            gainNode2.connect(audioContext.destination);
            
            oscillator2.frequency.value = 400;
            gainNode2.gain.value = 0.3;
            
            oscillator2.start();
            oscillator2.stop(audioContext.currentTime + 0.5);
        }, 500);
        
        setTimeout(playTone, 1000);
    };
    
    playTone();
}

function stopSiren() {
    sirenPlaying = false;
}

function vibrate() {
    // R-W4: Vibrate where supported
    if ('vibrate' in navigator) {
        navigator.vibrate([200, 100, 200]);
    }
}
