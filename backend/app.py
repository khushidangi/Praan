"""FastAPI backend for Praan field unit and city layer.

Endpoints:
- WebSocket /ws/telemetry - Live probe telemetry stream
- POST /api/inspection - Record completed inspection
- GET /api/sites - List monitored sites with history
- GET /api/sites/{site_id}/history - Site-specific inspection history
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from pathlib import Path
import json
import time
import asyncio

from backend.state_store import StateStore
from backend.simulated_probe import SimulatedProbe
from safety.engine_v2 import RuleEngine
from safety.config import get_config
from pipeline.guidance import GuidanceGenerator
from pipeline.voice import VoiceGenerator


app = FastAPI(title="Praan Safety System")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
state = StateStore()
guidance_gen = GuidanceGenerator(use_genie=False)
voice_gen = VoiceGenerator(language="hi")
safety_config = get_config()
rule_engine = RuleEngine(safety_config)

# Simulated probe (will be replaced by real USB-serial connection)
simulated_probe = SimulatedProbe(scenario="safe")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                dead_connections.append(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            self.active_connections.remove(connection)

manager = ConnectionManager()

# Background task for probe reading
probe_task_running = False

async def probe_broadcast_loop():
    """Single background task that reads probe and broadcasts to all clients."""
    while probe_task_running:
        try:
            # Read probe frame
            frame = simulated_probe.read_frame()

            # Evaluate safety decision
            decision_obj = rule_engine.evaluate(frame)
            decision = decision_obj.to_dict()

            # Generate guidance
            guidance = guidance_gen.generate(decision, language="hi")

            # Broadcast to all connected clients
            await manager.broadcast({
                "type": "update",
                "frame": frame,
                "decision": decision,
                "guidance": guidance,
            })

            await asyncio.sleep(2.0)  # Match probe polling interval
        except Exception as e:
            print(f"Probe broadcast error: {e}")
            await asyncio.sleep(2.0)


@app.on_event("startup")
async def startup_event():
    """Start the probe broadcast task."""
    global probe_task_running
    probe_task_running = True
    asyncio.create_task(probe_broadcast_loop())


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the probe broadcast task."""
    global probe_task_running
    probe_task_running = False


# ──────────────────────────────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────────────────────────────

class InspectionRecord(BaseModel):
    site_id: str
    site_name: str
    decision: str
    risk_tier: str
    violated_thresholds: List[str]
    readings: Dict
    guidance_text: str
    inspector_notes: Optional[str] = None


class SiteInfo(BaseModel):
    site_id: str
    site_name: str
    location: Dict[str, float]  # lat, lon
    last_inspection_ts: Optional[float] = None
    last_decision: Optional[str] = None
    inspection_count: int = 0
    hazard_count: int = 0


# ──────────────────────────────────────────────────────────────────────
# WebSocket: Live Telemetry
# ──────────────────────────────────────────────────────────────────────

@app.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket):
    """Live probe telemetry + safety decisions via WebSocket."""
    await manager.connect(websocket)

    try:
        # Send initial status
        await websocket.send_json({
            "type": "status",
            "message": "Connected to Praan safety system",
            "mode": "simulated",  # Will be "hardware" when Arduino connected
        })

        # Keep connection alive and listen for client messages
        while True:
            # Just keep the connection open; broadcasts happen from probe_broadcast_loop
            try:
                await websocket.receive_text()
            except:
                break
            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected from telemetry stream")
    except Exception as e:
        manager.disconnect(websocket)
        print(f"WebSocket error: {e}")


# ──────────────────────────────────────────────────────────────────────
# REST API: Inspection Records
# ──────────────────────────────────────────────────────────────────────

@app.post("/api/inspection")
async def record_inspection(record: InspectionRecord):
    """Record a completed inspection."""
    inspection_id = state.save_inspection(
        site_id=record.site_id,
        site_name=record.site_name,
        decision=record.decision,
        risk_tier=record.risk_tier,
        violated_thresholds=record.violated_thresholds,
        readings=record.readings,
        guidance_text=record.guidance_text,
        inspector_notes=record.inspector_notes,
    )

    return {
        "success": True,
        "inspection_id": inspection_id,
        "message": "Inspection recorded successfully",
    }


@app.get("/api/sites")
async def list_sites() -> List[SiteInfo]:
    """List all monitored sites with summary statistics."""
    sites = state.get_all_sites()
    return [SiteInfo(**s) for s in sites]


@app.get("/api/sites/{site_id}/history")
async def site_history(site_id: str, limit: int = 20):
    """Get inspection history for a specific site."""
    history = state.get_site_history(site_id, limit=limit)
    return {"site_id": site_id, "inspections": history}


# ──────────────────────────────────────────────────────────────────────
# Control: Change simulation scenario
# ──────────────────────────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    scenario: str


@app.post("/api/simulate/scenario")
async def set_scenario(request: ScenarioRequest):
    """Change simulated probe scenario (for demo purposes)."""
    valid_scenarios = ["safe", "h2s_buildup", "o2_depletion", "sensor_fault", "mixed_hazard"]
    if request.scenario not in valid_scenarios:
        raise HTTPException(400, f"Invalid scenario. Choose from: {valid_scenarios}")

    simulated_probe.set_scenario(request.scenario)
    return {
        "success": True,
        "scenario": request.scenario,
        "message": f"Scenario changed to: {request.scenario}",
    }


@app.get("/city")
async def city_dashboard():
    """Serve city layer dashboard."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Praan City Layer</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #f5f5f5;
                padding: 20px;
            }
            .container { max-width: 1400px; margin: 0 auto; }
            header {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 { font-size: 24px; color: #333; }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .stat-label { font-size: 12px; color: #666; margin-bottom: 8px; }
            .stat-value { font-size: 32px; font-weight: 700; color: #333; }
            .sites-table {
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 15px; text-align: left; }
            th { background: #f8f9fa; font-weight: 600; color: #333; }
            tr:not(:last-child) { border-bottom: 1px solid #e9ecef; }
            .decision-badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }
            .decision-GO { background: #d4edda; color: #155724; }
            .decision-CAUTION { background: #fff3cd; color: #856404; }
            .decision-NO_GO { background: #f8d7da; color: #721c24; }
            .decision-UNKNOWN { background: #e2e3e5; color: #383d41; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🏙️ Praan City Layer - Municipal Dashboard</h1>
            </header>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Sites</div>
                    <div class="stat-value" id="totalSites">--</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Total Inspections</div>
                    <div class="stat-value" id="totalInspections">--</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Hazardous Sites</div>
                    <div class="stat-value" id="hazardousSites">--</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Pending Sync</div>
                    <div class="stat-value" id="pendingSync">0</div>
                </div>
            </div>

            <div class="sites-table">
                <table>
                    <thead>
                        <tr>
                            <th>Site ID</th>
                            <th>Site Name</th>
                            <th>Last Inspection</th>
                            <th>Last Decision</th>
                            <th>Total Inspections</th>
                            <th>Hazard Count</th>
                        </tr>
                    </thead>
                    <tbody id="sitesTableBody">
                        <tr>
                            <td colspan="6" style="text-align: center; color: #999;">
                                Loading sites...
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function loadSites() {
                try {
                    const response = await fetch('/api/sites');
                    const sites = await response.json();

                    // Update stats
                    document.getElementById('totalSites').textContent = sites.length;
                    
                    const totalInspections = sites.reduce((sum, s) => sum + s.inspection_count, 0);
                    document.getElementById('totalInspections').textContent = totalInspections;
                    
                    const hazardousSites = sites.filter(s => s.hazard_count > 0).length;
                    document.getElementById('hazardousSites').textContent = hazardousSites;

                    // Update table
                    const tbody = document.getElementById('sitesTableBody');
                    if (sites.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">No sites recorded yet</td></tr>';
                        return;
                    }

                    tbody.innerHTML = sites.map(site => {
                        const lastInspection = site.last_inspection_ts 
                            ? new Date(site.last_inspection_ts * 1000).toLocaleString()
                            : 'Never';
                        
                        const decisionBadge = site.last_decision
                            ? `<span class="decision-badge decision-${site.last_decision}">${site.last_decision.replace('_', ' ')}</span>`
                            : '--';

                        return `
                            <tr>
                                <td>${site.site_id}</td>
                                <td>${site.site_name}</td>
                                <td>${lastInspection}</td>
                                <td>${decisionBadge}</td>
                                <td>${site.inspection_count}</td>
                                <td>${site.hazard_count}</td>
                            </tr>
                        `;
                    }).join('');
                } catch (err) {
                    console.error('Failed to load sites:', err);
                }
            }

            // Load sites on page load and refresh every 10 seconds
            loadSites();
            setInterval(loadSites, 10000);
        </script>
    </body>
    </html>
    """)


# ──────────────────────────────────────────────────────────────────────
# Static files & root
# ──────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint - landing page."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Praan Safety System</title>
        <style>
            body {
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            h1 { color: #333; }
            .status { 
                padding: 20px; 
                background: white; 
                border-radius: 8px; 
                margin: 20px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .links { margin-top: 30px; }
            .links a { 
                display: inline-block;
                padding: 10px 20px;
                background: #0066cc;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin-right: 10px;
            }
            .links a:hover { background: #0052a3; }
        </style>
    </head>
    <body>
        <h1>🛡️ Praan Safety System</h1>
        <div class="status">
            <h2>System Status</h2>
            <p>✅ Backend running</p>
            <p>⚙️ Mode: Simulated probe</p>
            <p>🔗 WebSocket endpoint: <code>/ws/telemetry</code></p>
        </div>
        <div class="links">
            <a href="/dashboard">Field Unit Dashboard</a>
            <a href="/city">City Layer Dashboard</a>
            <a href="/docs">API Documentation</a>
        </div>
    </body>
    </html>
    """)


def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        import sys
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent.parent
    
    return base_path / relative_path


@app.get("/dashboard")
async def dashboard():
    """Serve field unit dashboard."""
    dashboard_path = resource_path("dashboard/field_unit.html")
    return FileResponse(dashboard_path)


@app.get("/api/ai/status")
async def ai_status():
    """AI status endpoint - shows real engine/provider status."""
    # Check if Genie is actually wired up
    engine = "template"  # Will be "genie" when NPU integrated
    provider = "none"    # Will be "NPU" or "CPU" when Genie is wired
    model = None
    latency_ms = None
    
    # Check citations
    citations_valid = safety_config.all_citations_valid
    missing_citations = safety_config.missing_citations if not citations_valid else []
    
    return {
        "engine": engine,
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "citations_valid": citations_valid,
        "missing_citations": missing_citations,
        "offline": True,
        "cloud_requests": 0
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": time.time(),
        "mode": "simulated",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
