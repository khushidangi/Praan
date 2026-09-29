// Worker WebSocket client implementation (R-W requirements)

let ws = null;
let sessionId = null;
let token = null;
let selectedLang = 'hi';
let lastMessageTime = 0;
let watchdogInterval = null;
let wakeLock = null;

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
        document.getElementById('noSignalScreen').classList.remove('active');
        
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
    stateContent.className = 'state-content';
    
    // Get state-specific config
    const state = data.state;
    const config = getStateConfig(state, data.reason);
    
    // Apply state class
    stateScreen.className = `state-screen active state-${state.toLowerCase()}`;
    
    // Update glyph
    document.getElementById('stateGlyph').textContent = config.glyph;
    
    // Update text (R-W2: show chosen language large, English small)
    const text = data.text || {};
    document.getElementById('statePrimary').textContent = text[selectedLang] || text.en || config.text;
    document.getElementById('stateSecondary').textContent = selectedLang !== 'en' ? text.en || '' : '';
    
    // Show note if present
    const noteEl = document.getElementById('stateNote');
    if (data.note) {
        noteEl.classList.remove('hidden');
        document.getElementById('stateNoteText').textContent = data.note;
    } else {
        noteEl.classList.add('hidden');
    }
    
    // Update actions (R-W8)
    updateActions(state, data);
    
    // Handle audio/vibration (R-W4)
    if (state === 'EVACUATE') {
        playSiren();
        vibrate();
    } else {
        stopSiren();
    }
}

function getStateConfig(state, reason) {
    const configs = {
        'HOLD': {
            glyph: '✋',
            text: 'Wait here. Do not enter.'
        },
        'STOP': {
            glyph: '⛔',
            text: 'Do not enter. The air is not safe.'
        },
        'GO': {
            glyph: '✓',
            text: 'You may enter. Stay in contact.'
        },
        'WARN': {
            glyph: '⚠',
            text: 'The air is getting worse. Get ready to leave.'
        },
        'EVACUATE': {
            glyph: '🚨',
            text: 'LEAVE NOW. Climb out immediately.'
        }
    };
    
    return configs[state] || configs['HOLD'];
}

function updateActions(state, data) {
    const actionsDiv = document.getElementById('stateActions');
    actionsDiv.innerHTML = '';
    
    // R-W8: "I'm entering" only in GO, "I'm out" in GO, WARN, EVACUATE
    if (state === 'GO') {
        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = "I'm entering";
        btn.onclick = () => {
            ws.send(JSON.stringify({ type: 'ack', what: 'entering' }));
        };
        actionsDiv.appendChild(btn);
    }
    
    if (state === 'GO' || state === 'WARN' || state === 'EVACUATE') {
        const btn = document.createElement('button');
        btn.className = 'pill-btn';
        btn.textContent = "I'm out";
        btn.onclick = () => {
            ws.send(JSON.stringify({ type: 'ack', what: 'exited' }));
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
    document.getElementById('stateScreen').classList.remove('active');
    document.getElementById('noSignalScreen').classList.add('active');
    updateConnectionStatus(false);
    stopSiren();
}

function updateConnectionStatus(connected) {
    const dot = document.getElementById('connectionDot');
    const text = document.getElementById('footerText');
    
    if (connected) {
        dot.classList.remove('disconnected');
        text.textContent = 'Connected';
    } else {
        dot.classList.add('disconnected');
        text.textContent = 'Disconnected';
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
