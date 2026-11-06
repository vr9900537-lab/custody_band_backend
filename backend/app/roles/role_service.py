"""
Role & Access Control Service
Maintains system authorization roles and permission sets.
"""

from typing import List, Dict, Any, Optional
from ..accounts.account_service import account_service
from ..accounts.account_schemas import AccountUpdate


class RoleService:
    DEFAULT_ROLES = {
        "admin": {
            "name": "admin",
            "display_name": "System Administrator",
            "description": "Full administrative control over all wearers, accounts, and system configuration",
            "permissions": [
                "manage_accounts", "manage_roles", "manage_devices",
                "send_commands", "manage_geofences", "manage_alerts",
                "view_live_gps", "view_playback", "export_data", "manage_integrations"
            ]
        },
        "supervisor": {
            "name": "supervisor",
            "display_name": "Watch Supervisor",
            "description": "Oversees active cases, manages alerts, commands, and geofences",
            "permissions": [
                "manage_devices", "send_commands", "manage_geofences",
                "manage_alerts", "view_live_gps", "view_playback", "export_data"
            ]
        },
        "field_officer": {
            "name": "field_officer",
            "display_name": "Field Officer",
            "description": "Monitors assigned wearers and responds to security breaches in real time",
            "permissions": [
                "view_devices", "view_live_gps", "view_playback",
                "send_commands", "manage_alerts"
            ]
        },
        "auditor": {
            "name": "auditor",
            "display_name": "Legal Auditor",
            "description": "Read-only access for court compliance verification and evidence export",
            "permissions": [
                "view_devices", "view_playback", "export_data"
            ]
        }
    }

    def list_roles(self) -> List[Dict[str, Any]]:
        return list(self.DEFAULT_ROLES.values())

    def get_role(self, role_name: str) -> Optional[Dict[str, Any]]:
        return self.DEFAULT_ROLES.get(role_name.lower())

    def assign_role(self, email: str, role_name: str) -> Dict[str, Any]:
        role = self.get_role(role_name)
        if not role:
            raise ValueError(f"Unknown role '{role_name}'")

        account_service.update_account(email, AccountUpdate())
        import sqlite3
        from pathlib import Path
        db_file = Path(__file__).resolve().parent.parent.parent / "custody_watch.db"
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute("UPDATE users SET role = ? WHERE email = ?", (role_name.lower(), email))
        conn.commit()
        conn.close()

        return {
            "email": email,
            "assigned_role": role_name.lower(),
            "role_title": role["display_name"],
            "permissions": role["permissions"]
        }


role_service = RoleService()

