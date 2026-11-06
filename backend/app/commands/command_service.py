"""
Watch Command Dispatch & Audit Service
Translates high-level operations into Huaten C05 protocol frames and logs audit history.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..receiver.tcp_server import send_command_to_device
from ..utils.datetime_utils import current_iso_timestamp

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DB = BASE_DIR / "custody_watch.db"


class CommandService:
    SUPPORTED_COMMANDS = {
        "CR": "Poll immediate live GPS coordinates",
        "RESET": "Reboot watch operating system",
        "POWEROFF": "Remotely power off the custody watch",
        "FACTORY": "Reset firmware settings to factory default",
        "UPLOAD": "Set telemetry reporting interval (e.g. UPLOAD,60)",
        "SETIP": "Update target server IP and port (e.g. SETIP,103.44.0.5,9001)",
        "VERNO": "Query watch firmware version"
    }

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS command_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                command_raw TEXT NOT NULL,
                command_type TEXT NOT NULL,
                dispatched_by TEXT,
                dispatched INTEGER DEFAULT 0,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def dispatch_command(
        self,
        device_id: str,
        command_type: str,
        parameters: Optional[str] = None,
        dispatched_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Constructs protocol command and transmits over raw TCP socket."""
        cmd_type = command_type.strip().upper()
        if parameters:
            raw_command = f"{cmd_type},{parameters}"
        else:
            raw_command = cmd_type

        # Send via TCP receiver
        delivered = send_command_to_device(device_id, raw_command)
        ts = current_iso_timestamp()

        # Audit log in database
        conn = sqlite3.connect(str(LOCAL_DB))
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO command_audit (device_id, command_raw, command_type, dispatched_by, dispatched, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (device_id, raw_command, cmd_type, dispatched_by, 1 if delivered else 0, ts))
        conn.commit()
        conn.close()

        return {
            "device_id": device_id,
            "command": raw_command,
            "command_type": cmd_type,
            "dispatched": delivered,
            "dispatched_by": dispatched_by,
            "timestamp": ts,
            "message": "Command transmitted to watch" if delivered else "Watch is sleeping or offline"
        }

    def get_command_history(self, device_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(str(LOCAL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if device_id:
            rows = cur.execute(
                "SELECT * FROM command_audit WHERE device_id = ? ORDER BY id DESC LIMIT ?",
                (device_id, limit)
            ).fetchall()
        else:
            rows = cur.execute(
                "SELECT * FROM command_audit ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        res = [dict(r) for r in rows]
        conn.close()
        return res

    def get_supported_commands(self) -> Dict[str, str]:
        return self.SUPPORTED_COMMANDS


command_service = CommandService()

