"""State persistence using SQLite for offline-first operation."""

import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
import uuid
import os


class StateStore:
    """Manages inspection records and site history in SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize state store.

        Args:
            db_path: Path to SQLite database file (defaults to praan_data.db)
        """
        if db_path is None:
            db_path = Path("praan_data.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()

        # Sites table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            site_id TEXT PRIMARY KEY,
            site_name TEXT NOT NULL,
            location_json TEXT,  -- JSON: {lat: ..., lon: ...}
            created_at REAL NOT NULL,
            last_inspection_ts REAL
        )
        """)

        # Inspections table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            inspection_id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            decision TEXT NOT NULL,
            risk_tier TEXT NOT NULL,
            violated_thresholds_json TEXT,  -- JSON array
            readings_json TEXT,              -- JSON object
            guidance_text TEXT,
            inspector_notes TEXT,
            synced INTEGER DEFAULT 0,
            FOREIGN KEY (site_id) REFERENCES sites(site_id)
        )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_site_ts ON inspections(site_id, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_synced ON inspections(synced)")

        self.conn.commit()
        self._seed_demo_data()

    def _seed_demo_data(self):
        """Create visible offline demo sites once for a fresh or empty hub."""
        if os.getenv("PRAAN_DEMO_DATA", "1").lower() in {"0", "false", "no"}:
            return
        cursor = self.conn.cursor()
        if cursor.execute("SELECT 1 FROM sites LIMIT 1").fetchone():
            return

        now = time.time()
        demo_sites = [
            ("MH-1049", "Manhole MH-1049 (Sector 4B Trunk Sewer)", 28.61, 77.21, "NO_GO", {"h2s_ppm": 14.2, "co_ppm": 18, "o2_pct": 19.8, "lel_pct": 2}),
            ("SC-0882", "Septic Chamber SC-0882 (Govt Hospital Ward 3)", 28.62, 77.22, "CAUTION", {"h2s_ppm": 8.1, "co_ppm": 12, "o2_pct": 20.1, "lel_pct": 4}),
            ("MH-0427", "Manhole MH-0427 (Market Square West)", 28.60, 77.20, "UNKNOWN", {"h2s_ppm": 0, "co_ppm": 0, "o2_pct": 0, "lel_pct": 0}),
            ("MH-0118", "Manhole MH-0118 (Railway Crossing Culvert)", 28.63, 77.19, "GO", {"h2s_ppm": 1.0, "co_ppm": 5, "o2_pct": 20.9, "lel_pct": 0.5}),
        ]
        for site_id, name, lat, lon, decision, readings in demo_sites:
            cursor.execute(
                "INSERT INTO sites (site_id, site_name, location_json, created_at, last_inspection_ts) VALUES (?, ?, ?, ?, ?)",
                (site_id, name, json.dumps({"lat": lat, "lon": lon}), now, now),
            )
            cursor.execute(
                """INSERT INTO inspections (
                    inspection_id, site_id, timestamp, decision, risk_tier,
                    violated_thresholds_json, readings_json, guidance_text,
                    inspector_notes, synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    str(uuid.uuid4()), site_id, now, decision,
                    "hazard" if decision == "NO_GO" else "caution" if decision in {"CAUTION", "UNKNOWN"} else "safe",
                    json.dumps(["h2s_ppm"] if decision == "NO_GO" else []),
                    json.dumps(readings),
                    "DEMO DATA: historical inspection placeholder",
                    "SIMULATED demo record",
                ),
            )
        self.conn.commit()

    def save_inspection(
        self,
        site_id: str,
        site_name: str,
        decision: str,
        risk_tier: str,
        violated_thresholds: List[str],
        readings: Dict,
        guidance_text: str,
        inspector_notes: Optional[str] = None,
    ) -> str:
        """Save an inspection record.

        Returns:
            inspection_id
        """
        inspection_id = str(uuid.uuid4())
        timestamp = time.time()

        cursor = self.conn.cursor()

        # Ensure site exists
        cursor.execute(
            """
            INSERT OR IGNORE INTO sites (site_id, site_name, location_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (site_id, site_name, json.dumps({"lat": 0, "lon": 0}), timestamp),
        )

        # Update site's last inspection timestamp
        cursor.execute(
            "UPDATE sites SET last_inspection_ts = ? WHERE site_id = ?",
            (timestamp, site_id),
        )

        # Insert inspection
        cursor.execute(
            """
            INSERT INTO inspections (
                inspection_id, site_id, timestamp, decision, risk_tier,
                violated_thresholds_json, readings_json, guidance_text,
                inspector_notes, synced
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                inspection_id,
                site_id,
                timestamp,
                decision,
                risk_tier,
                json.dumps(violated_thresholds),
                json.dumps(readings),
                guidance_text,
                inspector_notes,
            ),
        )

        self.conn.commit()
        return inspection_id

    def get_all_sites(self) -> List[Dict]:
        """Get all sites with summary statistics."""
        cursor = self.conn.cursor()
        cursor.execute("""
        SELECT 
            s.site_id,
            s.site_name,
            s.location_json,
            s.last_inspection_ts,
            (SELECT decision FROM inspections WHERE site_id = s.site_id 
             ORDER BY timestamp DESC LIMIT 1) as last_decision,
            COUNT(i.inspection_id) as inspection_count,
            SUM(CASE WHEN i.decision = 'NO_GO' THEN 1 ELSE 0 END) as hazard_count
        FROM sites s
        LEFT JOIN inspections i ON s.site_id = i.site_id
        GROUP BY s.site_id
        ORDER BY s.last_inspection_ts DESC
        """)

        sites = []
        for row in cursor.fetchall():
            sites.append({
                "site_id": row["site_id"],
                "site_name": row["site_name"],
                "location": json.loads(row["location_json"] or "{}"),
                "last_inspection_ts": row["last_inspection_ts"],
                "last_decision": row["last_decision"],
                "inspection_count": row["inspection_count"] or 0,
                "hazard_count": row["hazard_count"] or 0,
            })

        return sites

    def get_site_history(self, site_id: str, limit: int = 20) -> List[Dict]:
        """Get inspection history for a site."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 
                inspection_id, timestamp, decision, risk_tier,
                violated_thresholds_json, readings_json, guidance_text,
                inspector_notes
            FROM inspections
            WHERE site_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (site_id, limit),
        )

        inspections = []
        for row in cursor.fetchall():
            inspections.append({
                "inspection_id": row["inspection_id"],
                "timestamp": row["timestamp"],
                "decision": row["decision"],
                "risk_tier": row["risk_tier"],
                "violated_thresholds": json.loads(row["violated_thresholds_json"]),
                "readings": json.loads(row["readings_json"]),
                "guidance_text": row["guidance_text"],
                "inspector_notes": row["inspector_notes"],
            })

        return inspections

    def get_unsynced_count(self) -> int:
        """Get count of inspections pending sync to city layer."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM inspections WHERE synced = 0")
        return cursor.fetchone()[0]

    def mark_synced(self, inspection_ids: List[str]):
        """Mark inspections as synced."""
        cursor = self.conn.cursor()
        placeholders = ",".join("?" * len(inspection_ids))
        cursor.execute(
            f"UPDATE inspections SET synced = 1 WHERE inspection_id IN ({placeholders})",
            inspection_ids,
        )
        self.conn.commit()

    def close(self):
        """Close database connection."""
        self.conn.close()
