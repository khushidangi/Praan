"""Worker WebSocket handler."""

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Optional

from session.manager import SessionManager
from session.auth import get_auth


class WorkerConnection:
    """Manages a single worker WebSocket connection."""
    
    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        worker_id: str,
        session_manager: SessionManager
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.worker_id = worker_id
        self.session_manager = session_manager
        self.last_seq = 0
        self.running = False
    
    async def handle(self):
        """Handle worker WebSocket connection."""
        await self.websocket.accept()
        self.running = True
        
        # Start heartbeat sender
        hb_task = asyncio.create_task(self._send_heartbeats())
        
        try:
            while self.running:
                # Receive messages from worker
                data = await self.websocket.receive_text()
                message = json.loads(data)
                
                await self._handle_worker_message(message)
                
        except WebSocketDisconnect:
            self.running = False
        except Exception as e:
            print(f"Worker WebSocket error: {e}")
            self.running = False
        finally:
            hb_task.cancel()
    
    async def send_state(self, state_data: Dict):
        """Send state update to worker (R-W2)."""
        # Get worker state from session manager
        worker_state = self.session_manager.get_worker_state(
            self.session_id,
            self.worker_id
        )
        
        # Get session for crew info
        session = self.session_manager.get_session(self.session_id)
        if not session:
            return
        
        worker = session.workers.get(self.worker_id)
        if not worker:
            return
        
        # Increment sequence number
        session.seq += 1
        
        # Build state message per 7.3 spec
        message = {
            "type": "state",
            "seq": session.seq,
            "state": worker_state.get("state"),
            "reason": worker_state.get("reason"),
            "text": self._get_canonical_text(worker_state, worker.lang),
            "audio_key": self._get_audio_key(worker_state),
            "note": worker_state.get("note"),
            "go_valid_seconds_left": worker_state.get("go_valid_seconds_left"),
            "elapsed_since_check_s": None,  # TODO: calculate from latest reading
            "task": None,  # TODO: task assignment
            "crew": {
                "total": len(session.workers),
                "checked_in": len(session.workers)
            }
        }
        
        try:
            await self.websocket.send_json(message)
        except:
            self.running = False
    
    async def _send_heartbeats(self):
        """Send heartbeat every 2 seconds."""
        while self.running:
            try:
                session = self.session_manager.get_session(self.session_id)
                if session:
                    session.seq += 1
                    await self.websocket.send_json({
                        "type": "hb",
                        "seq": session.seq
                    })
                await asyncio.sleep(2.0)
            except:
                self.running = False
                break
    
    async def _handle_worker_message(self, message: Dict):
        """Handle incoming messages from worker."""
        msg_type = message.get("type")
        
        if msg_type == "hello":
            # Worker joining
            self.session_manager.worker_join(
                session_id=self.session_id,
                worker_id=self.worker_id,
                name=message.get("name", "Worker"),
                lang=message.get("lang", "en"),
                consent=message.get("consent", False)
            )
            await self.send_state({})
        
        elif msg_type == "loc":
            # Location update (R-W6)
            self.session_manager.update_worker_location(
                session_id=self.session_id,
                worker_id=self.worker_id,
                lat=message.get("lat"),
                lon=message.get("lon"),
                accuracy=message.get("accuracy", 999)
            )
        
        elif msg_type == "ack":
            # Acknowledgment
            what = message.get("what")
            if what == "entering":
                self.session_manager.worker_entering(self.session_id, self.worker_id)
                await self.send_state({})
            elif what == "exited":
                self.session_manager.worker_exited(self.session_id, self.worker_id)
                await self.send_state({})
        
        elif msg_type == "hb":
            # Heartbeat from worker
            self.session_manager.update_worker_heartbeat(self.session_id, self.worker_id)
    
    def _get_canonical_text(self, worker_state: Dict, lang: str) -> Dict:
        """Get canonical text in all languages (R-G3, R-W2)."""
        # Simplified - load from guidance/canonical/ in production
        state = worker_state.get("state")
        reason = worker_state.get("reason")
        
        texts = {
            "HOLD": {
                "en": "Wait here. Do not enter. The supervisor will tell you when.",
                "hi": "यहीं रुकें। अंदर न जाएँ। सुपरवाइज़र बताएँगे कब जाना है।",
                "pa": "ਇੱਥੇ ਰੁਕੋ। ਅੰਦਰ ਨਾ ਜਾਓ। ਸੁਪਰਵਾਈਜ਼ਰ ਦੱਸਣਗੇ ਕਦੋਂ ਜਾਣਾ ਹੈ।"
            },
            "STOP": {
                "en": "Do not enter. The air is not safe.",
                "hi": "अंदर न जाएँ। हवा सुरक्षित नहीं है।",
                "pa": "ਅੰਦਰ ਨਾ ਜਾਓ। ਹਵਾ ਸੁਰੱਖਿਅਤ ਨਹੀਂ ਹੈ।"
            },
            "GO": {
                "en": "You may enter. Stay in contact.",
                "hi": "आप अंदर जा सकते हैं। संपर्क में रहें।",
                "pa": "ਤੁਸੀਂ ਅੰਦਰ ਜਾ ਸਕਦੇ ਹੋ। ਸੰਪਰਕ ਵਿੱਚ ਰਹੋ।"
            },
            "WARN": {
                "en": "The air is getting worse. Get ready to leave.",
                "hi": "हवा बिगड़ रही है। बाहर निकलने के लिए तैयार रहें।",
                "pa": "ਹਵਾ ਵਿਗੜ ਰਹੀ ਹੈ। ਬਾਹਰ ਨਿਕਲਣ ਲਈ ਤਿਆਰ ਰਹੋ।"
            },
            "EVACUATE": {
                "en": "LEAVE NOW. Climb out immediately.",
                "hi": "अभी बाहर निकलें। तुरंत ऊपर आएँ।",
                "pa": "ਹੁਣੇ ਬਾਹਰ ਨਿਕਲੋ। ਤੁਰੰਤ ਉੱਪਰ ਆਓ।"
            }
        }
        
        return texts.get(state, texts["HOLD"])
    
    def _get_audio_key(self, worker_state: Dict) -> str:
        """Get audio clip key for this state."""
        state = worker_state.get("state")
        reason = worker_state.get("reason")
        
        if state == "HOLD":
            if reason == "SUPERVISOR_HOLD":
                return "hold_supervisor"
            elif reason == "AWAITING_READING":
                return "hold_reading"
            elif reason == "AWAITING_AUTHORIZATION":
                return "hold_authorization"
            else:
                return "hold_awaiting_supervisor"
        elif state == "STOP":
            if reason == "CANNOT_VERIFY":
                return "stop_unknown"
            else:
                return "stop_air"
        elif state == "GO":
            return "go"
        elif state == "WARN":
            return "warn"
        elif state == "EVACUATE":
            return "evacuate_inside"
        
        return "hold_awaiting_supervisor"
