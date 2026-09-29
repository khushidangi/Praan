"""Session event logging."""

import time
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import sqlite3


@dataclass
class SessionEvent:
    """A state transition or significant event in a session."""
    id: Optional[int]
    session_id: str
    ts: float
    from_state: Optional[str]
    to_state: str
    cause: str
    actor: str  # "system", "supervisor", "worker:<id>"
    decision_id: Optional[str]
    payload_json: Optional[str]
    
    def to_dict(self) -> Dict:
        """Convert to dict for API responses."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "ts": self.ts,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "cause": self.cause,
            "actor": self.actor,
            "decision_id": self.decision_id,
            "payload": json.loads(self.payload_json) if self.payload_json else None
        }


class EventLog:
    """Append-only event log for sessions."""
    
    def __init__(self, db_path: str = "praan.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts REAL NOT NULL,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    cause TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    decision_id TEXT,
                    payload_json TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_events_session 
                ON session_events(session_id, ts)
            """)
    
    def log_transition(
        self,
        session_id: str,
        from_state: Optional[str],
        to_state: str,
        cause: str,
        actor: str,
        decision_id: Optional[str] = None,
        payload: Optional[Dict] = None
    ) -> int:
        """Log a state transition (R-N9).
        
        Returns:
            Event ID
        """
        ts = time.time()
        payload_json = json.dumps(payload) if payload else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO session_events 
                (session_id, ts, from_state, to_state, cause, actor, decision_id, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, ts, from_state, to_state, cause, actor, decision_id, payload_json))
            return cursor.lastrowid
    
    def get_session_events(self, session_id: str, limit: int = 100) -> List[SessionEvent]:
        """Get events for a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM session_events
                WHERE session_id = ?
                ORDER BY ts DESC
                LIMIT ?
            """, (session_id, limit))
            
            rows = cursor.fetchall()
            return [SessionEvent(**dict(row)) for row in rows]
    
    def get_timeline(self, session_id: str) -> List[Dict]:
        """Get formatted timeline for UI."""
        events = self.get_session_events(session_id)
        
        timeline = []
        for event in reversed(events):  # Chronological order
            timeline.append({
                "ts": event.ts,
                "message": self._format_event(event),
                "actor": event.actor,
                "state": event.to_state
            })
        
        return timeline
    
    def _format_event(self, event: SessionEvent) -> str:
        """Format event for human reading."""
        if event.from_state:
            return f"{event.from_state} → {event.to_state}: {event.cause}"
        else:
            return f"Session started: {event.cause}"
