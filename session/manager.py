"""Session state machine - the single owner of worker-facing state (R-N1)."""

import time
import uuid
from typing import Dict, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

from session.events import EventLog


class SessionState(Enum):
    """Session states from Section 5."""
    PREP = "PREP"
    SAMPLING = "SAMPLING"
    BLOCKED = "BLOCKED"
    READY = "READY"
    AUTHORIZED = "AUTHORIZED"
    IN_ENTRY = "IN_ENTRY"
    EVACUATE = "EVACUATE"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class WorkerState(Enum):
    """What workers see."""
    HOLD = "HOLD"
    STOP = "STOP"
    WARN = "WARN"
    GO = "GO"
    EVACUATE = "EVACUATE"


@dataclass
class Worker:
    """Worker in a session."""
    worker_id: str
    name: str
    lang: str
    checked_in_at: float
    last_hb: float
    location: Optional[Dict] = None
    presence: str = "UNVERIFIED"  # AT_SITE, NEARBY, AWAY, UNVERIFIED, OFF
    in_entry: bool = False


@dataclass
class Session:
    """A session represents one job at one site."""
    session_id: str
    site_id: str
    site_name: str
    supervisor: str
    started_at: float
    state: SessionState = SessionState.PREP
    
    # Workers
    workers: Dict[str, Worker] = field(default_factory=dict)
    workers_in_entry: Set[str] = field(default_factory=set)
    
    # Hold overlay
    hold_flag: bool = False
    hold_note: Optional[str] = None
    
    # Authorization
    go_authorized_at: Optional[float] = None
    go_expires_at: Optional[float] = None
    
    # Latest engine decision
    latest_decision: Optional[Dict] = None
    latest_decision_id: Optional[str] = None
    
    # Sequence counter for messages
    seq: int = 0
    
    # Metadata
    simulated: bool = True
    closed_at: Optional[float] = None


class SessionManager:
    """The session state machine."""
    
    def __init__(self, event_log: Optional[EventLog] = None):
        self.sessions: Dict[str, Session] = {}
        self.event_log = event_log or EventLog()
        self.go_valid_minutes = 30  # From config
    
    def create_session(
        self,
        site_id: str,
        site_name: str,
        supervisor: str,
        simulated: bool = True
    ) -> Session:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            site_id=site_id,
            site_name=site_name,
            supervisor=supervisor,
            started_at=time.time(),
            simulated=simulated
        )
        
        self.sessions[session_id] = session
        
        self.event_log.log_transition(
            session_id=session_id,
            from_state=None,
            to_state=SessionState.PREP.value,
            cause="session_created",
            actor=f"supervisor:{supervisor}"
        )
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)
    
    def worker_join(
        self,
        session_id: str,
        worker_id: str,
        name: str,
        lang: str,
        consent: bool
    ) -> bool:
        """Worker joins a session (R-W1)."""
        session = self.get_session(session_id)
        if not session or session.state == SessionState.CLOSED:
            return False
        
        if not consent:
            return False
        
        worker = Worker(
            worker_id=worker_id,
            name=name,
            lang=lang,
            checked_in_at=time.time(),
            last_hb=time.time()
        )
        
        session.workers[worker_id] = worker
        
        self.event_log.log_transition(
            session_id=session_id,
            from_state=session.state.value,
            to_state=session.state.value,
            cause="worker_joined",
            actor=f"worker:{worker_id}",
            payload={"name": name, "lang": lang}
        )
        
        return True
    
    def update_worker_location(
        self,
        session_id: str,
        worker_id: str,
        lat: float,
        lon: float,
        accuracy: float
    ):
        """Update worker location (R-W6)."""
        session = self.get_session(session_id)
        if not session:
            return
        
        worker = session.workers.get(worker_id)
        if not worker:
            return
        
        worker.location = {"lat": lat, "lon": lon, "accuracy": accuracy}
        
        # Compute presence (simplified - would use site coordinates in production)
        if accuracy > 50:
            worker.presence = "UNVERIFIED"
        else:
            worker.presence = "AT_SITE"  # Simplified
    
    def update_worker_heartbeat(self, session_id: str, worker_id: str):
        """Update worker heartbeat."""
        session = self.get_session(session_id)
        if not session:
            return
        
        worker = session.workers.get(worker_id)
        if worker:
            worker.last_hb = time.time()
    
    def transition(
        self,
        session_id: str,
        to_state: SessionState,
        cause: str,
        actor: str,
        decision_id: Optional[str] = None
    ) -> bool:
        """Perform a state transition (R-N9)."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        from_state = session.state
        session.state = to_state
        session.seq += 1
        
        self.event_log.log_transition(
            session_id=session_id,
            from_state=from_state.value,
            to_state=to_state.value,
            cause=cause,
            actor=actor,
            decision_id=decision_id
        )
        
        return True
    
    def process_decision(self, session_id: str, decision: Dict) -> bool:
        """Process a rule engine decision and update session state.
        
        This implements R-N2 through R-N5.
        """
        session = self.get_session(session_id)
        if not session or session.state == SessionState.CLOSED:
            return False
        
        session.latest_decision = decision
        session.latest_decision_id = decision.get("decision_id")
        
        engine_decision = decision.get("decision")
        current_state = session.state
        
        # R-N3: NO_GO/UNKNOWN during entry → EVACUATE
        if engine_decision in ["NO_GO", "UNKNOWN"]:
            if current_state in [SessionState.AUTHORIZED, SessionState.IN_ENTRY]:
                self.transition(
                    session_id, 
                    SessionState.EVACUATE,
                    f"engine_{engine_decision.lower()}",
                    "system",
                    decision.get("decision_id")
                )
                return True
            
            # R-N2: Before entry → BLOCKED
            if current_state in [SessionState.SAMPLING, SessionState.PREP]:
                self.transition(
                    session_id,
                    SessionState.BLOCKED,
                    f"engine_{engine_decision.lower()}",
                    "system",
                    decision.get("decision_id")
                )
                return True
        
        # R-N4: CAUTION during entry → show WARN
        if engine_decision == "CAUTION":
            if current_state in [SessionState.AUTHORIZED, SessionState.IN_ENTRY]:
                # Stay in current state but workers see WARN
                pass
            elif current_state == SessionState.SAMPLING:
                # Before entry, CAUTION is BLOCKED
                self.transition(
                    session_id,
                    SessionState.BLOCKED,
                    "engine_caution",
                    "system",
                    decision.get("decision_id")
                )
                return True
        
        # R-N5: Stable GO → READY (keep workers on HOLD)
        if engine_decision == "GO":
            if current_state == SessionState.SAMPLING:
                self.transition(
                    session_id,
                    SessionState.READY,
                    "engine_go",
                    "system",
                    decision.get("decision_id")
                )
                return True
            elif current_state == SessionState.BLOCKED:
                # Recovered from blocked
                self.transition(
                    session_id,
                    SessionState.READY,
                    "engine_go_recovery",
                    "system",
                    decision.get("decision_id")
                )
                return True
        
        return False
    
    def deploy_probe(self, session_id: str, actor: str) -> bool:
        """Transition to SAMPLING state."""
        session = self.get_session(session_id)
        if not session or session.state != SessionState.PREP:
            return False
        
        return self.transition(
            session_id,
            SessionState.SAMPLING,
            "probe_deployed",
            actor
        )
    
    def set_hold(self, session_id: str, note: Optional[str], actor: str) -> bool:
        """Set supervisor hold (R-N6)."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.hold_flag = True
        session.hold_note = note
        
        self.event_log.log_transition(
            session_id=session_id,
            from_state=session.state.value,
            to_state=session.state.value,
            cause="supervisor_hold_set",
            actor=actor,
            payload={"note": note}
        )
        
        return True
    
    def release_hold(self, session_id: str, actor: str) -> bool:
        """Release supervisor hold."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.hold_flag = False
        session.hold_note = None
        
        self.event_log.log_transition(
            session_id=session_id,
            from_state=session.state.value,
            to_state=session.state.value,
            cause="supervisor_hold_released",
            actor=actor
        )
        
        return True
    
    def authorize_entry(self, session_id: str, actor: str) -> bool:
        """Authorize entry (R-N5, R-N6).
        
        Requirements:
        - State must be READY
        - No supervisor hold
        - Latest decision must be GO
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Check preconditions
        if session.state != SessionState.READY:
            return False
        
        if session.hold_flag:
            return False
        
        if not session.latest_decision or session.latest_decision.get("decision") != "GO":
            return False
        
        # Authorize
        now = time.time()
        session.go_authorized_at = now
        session.go_expires_at = now + (self.go_valid_minutes * 60)  # R-N7
        
        return self.transition(
            session_id,
            SessionState.AUTHORIZED,
            "supervisor_authorized",
            actor
        )
    
    def worker_entering(self, session_id: str, worker_id: str) -> bool:
        """Worker taps 'I'm entering' (R-W8)."""
        session = self.get_session(session_id)
        if not session or session.state != SessionState.AUTHORIZED:
            return False
        
        worker = session.workers.get(worker_id)
        if not worker:
            return False
        
        # Check GO still valid
        if not session.go_expires_at or time.time() > session.go_expires_at:
            return False
        
        worker.in_entry = True
        session.workers_in_entry.add(worker_id)
        
        # Transition to IN_ENTRY if first worker
        if session.state == SessionState.AUTHORIZED:
            self.transition(
                session_id,
                SessionState.IN_ENTRY,
                "worker_entering",
                f"worker:{worker_id}"
            )
        
        return True
    
    def worker_exited(self, session_id: str, worker_id: str) -> bool:
        """Worker taps 'I'm out' (R-W8)."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        worker = session.workers.get(worker_id)
        if not worker:
            return False
        
        worker.in_entry = False
        session.workers_in_entry.discard(worker_id)
        
        self.event_log.log_transition(
            session_id=session_id,
            from_state=session.state.value,
            to_state=session.state.value,
            cause="worker_exited",
            actor=f"worker:{worker_id}"
        )
        
        return True
    
    def evacuate(self, session_id: str, actor: str) -> bool:
        """Supervisor manually triggers evacuation."""
        session = self.get_session(session_id)
        if not session or session.state == SessionState.CLOSED:
            return False
        
        return self.transition(
            session_id,
            SessionState.EVACUATE,
            "supervisor_evacuate",
            actor
        )
    
    def all_clear(self, session_id: str, actor: str, override: bool = False) -> bool:
        """Clear evacuation (R-N8)."""
        session = self.get_session(session_id)
        if not session or session.state != SessionState.EVACUATE:
            return False
        
        # Check all workers are out
        if not override and len(session.workers_in_entry) > 0:
            return False
        
        return self.transition(
            session_id,
            SessionState.CLOSING,
            "all_clear" if not override else "all_clear_override",
            actor
        )
    
    def close_session(self, session_id: str, actor: str) -> bool:
        """Close the session."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.closed_at = time.time()
        
        # Purge location data (R-X3) - keep only at_site timeline
        for worker in session.workers.values():
            worker.location = None
        
        return self.transition(
            session_id,
            SessionState.CLOSED,
            "session_closed",
            actor
        )
    
    def get_worker_state(self, session_id: str, worker_id: str) -> Dict:
        """Get what a worker should see (R-N1, R-W2)."""
        session = self.get_session(session_id)
        if not session:
            return {
                "state": WorkerState.STOP.value,
                "reason": "session_not_found"
            }
        
        worker = session.workers.get(worker_id)
        if not worker:
            return {
                "state": WorkerState.STOP.value,
                "reason": "not_checked_in"
            }
        
        # Map session state to worker state
        if session.state == SessionState.EVACUATE:
            return {
                "state": WorkerState.EVACUATE.value,
                "reason": "EVACUATE"
            }
        
        if session.state in [SessionState.PREP, SessionState.SAMPLING, SessionState.READY, SessionState.CLOSING]:
            reason_map = {
                SessionState.PREP: "AWAITING_SUPERVISOR",
                SessionState.SAMPLING: "AWAITING_READING",
                SessionState.READY: "AWAITING_AUTHORIZATION",
                SessionState.CLOSING: "SESSION_ENDING"
            }
            return {
                "state": WorkerState.HOLD.value,
                "reason": reason_map.get(session.state, "AWAITING_SUPERVISOR")
            }
        
        if session.state == SessionState.BLOCKED:
            # Check decision
            if session.latest_decision:
                engine_decision = session.latest_decision.get("decision")
                if engine_decision == "UNKNOWN":
                    return {
                        "state": WorkerState.STOP.value,
                        "reason": "CANNOT_VERIFY"
                    }
                else:
                    return {
                        "state": WorkerState.STOP.value,
                        "reason": "AIR_NOT_SAFE"
                    }
            return {
                "state": WorkerState.STOP.value,
                "reason": "AIR_NOT_SAFE"
            }
        
        if session.state == SessionState.AUTHORIZED:
            # Check if hold is set
            if session.hold_flag:
                return {
                    "state": WorkerState.HOLD.value,
                    "reason": "SUPERVISOR_HOLD",
                    "note": session.hold_note
                }
            
            # Check GO expiry
            if session.go_expires_at and time.time() > session.go_expires_at:
                return {
                    "state": WorkerState.HOLD.value,
                    "reason": "GO_EXPIRED"
                }
            
            return {
                "state": WorkerState.GO.value,
                "go_valid_seconds_left": int(session.go_expires_at - time.time()) if session.go_expires_at else None
            }
        
        if session.state == SessionState.IN_ENTRY:
            # Check if CAUTION
            if session.latest_decision and session.latest_decision.get("decision") == "CAUTION":
                return {
                    "state": WorkerState.WARN.value,
                    "reason": "AIR_DEGRADING"
                }
            
            # Check GO expiry
            if session.go_expires_at and time.time() > session.go_expires_at:
                return {
                    "state": WorkerState.HOLD.value,
                    "reason": "GO_EXPIRED"
                }
            
            return {
                "state": WorkerState.GO.value if worker.in_entry else WorkerState.HOLD.value,
                "go_valid_seconds_left": int(session.go_expires_at - time.time()) if session.go_expires_at else None
            }
        
        # Default: HOLD
        return {
            "state": WorkerState.HOLD.value,
            "reason": "AWAITING_SUPERVISOR"
        }
