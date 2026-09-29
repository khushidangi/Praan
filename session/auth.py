"""Token-based authentication for sessions."""

import hmac
import hashlib
import time
import json
from typing import Dict, Optional


class TokenAuth:
    """HMAC-based token authentication."""
    
    def __init__(self, secret: bytes):
        self.secret = secret
    
    def generate_token(self, session_id: str, role: str, exp_hours: int = 24) -> str:
        """Generate a signed token for a session.
        
        Args:
            session_id: Session identifier
            role: "worker" or "supervisor"
            exp_hours: Token expiration in hours
            
        Returns:
            Base64-encoded signed token
        """
        exp = int(time.time()) + (exp_hours * 3600)
        payload = {
            "session_id": session_id,
            "role": role,
            "exp": exp
        }
        
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        signature = hmac.new(self.secret, payload_bytes, hashlib.sha256).hexdigest()
        
        token_data = {
            "payload": payload,
            "signature": signature
        }
        
        return json.dumps(token_data)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify and decode a token.
        
        Args:
            token: Token string to verify
            
        Returns:
            Payload dict if valid, None otherwise
        """
        try:
            token_data = json.loads(token)
            payload = token_data["payload"]
            signature = token_data["signature"]
            
            # Verify signature
            payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
            expected_sig = hmac.new(self.secret, payload_bytes, hashlib.sha256).hexdigest()
            
            if not hmac.compare_digest(signature, expected_sig):
                return None
            
            # Check expiration
            if time.time() > payload["exp"]:
                return None
            
            return payload
            
        except (json.JSONDecodeError, KeyError, TypeError):
            return None
    
    def generate_supervisor_token_from_pin(self, pin: str, exp_hours: int = 168) -> str:
        """Generate supervisor token from PIN (for demo/testing).
        
        Args:
            pin: Supervisor PIN
            exp_hours: Token expiration (default 1 week)
            
        Returns:
            Supervisor token
        """
        # In production, verify PIN against database
        # For now, any 4+ digit PIN works
        if len(pin) < 4:
            raise ValueError("PIN must be at least 4 digits")
        
        session_id = "supervisor_global"  # Supervisor can access all sessions
        return self.generate_token(session_id, "supervisor", exp_hours)


# Global auth instance (initialized with hub secret)
_auth: Optional[TokenAuth] = None


def init_auth(secret: Optional[bytes] = None):
    """Initialize global auth instance."""
    global _auth
    if secret is None:
        # Generate random secret if none provided
        import secrets
        secret = secrets.token_bytes(32)
    _auth = TokenAuth(secret)


def get_auth() -> TokenAuth:
    """Get global auth instance."""
    if _auth is None:
        init_auth()
    return _auth
