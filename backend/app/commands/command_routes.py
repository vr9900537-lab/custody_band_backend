"""
Command API Routes
Endpoints for transmitting remote commands to custody bands and inspecting audit trails.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from ..commands.command_schemas import SendCommandRequest
from ..commands.command_service import command_service
from ..core.dependencies import get_current_user

router = APIRouter(prefix="/commands", tags=["Commands"])


@router.post("/send", response_model=Dict[str, Any])
def send_command(
    cmd_req: SendCommandRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Transmit a protocol command to a custody watch:
    - `CR`: Poll live GPS fix immediately
    - `RESET`: Reboot watch
    - `UPLOAD`: Set reporting interval in seconds (e.g. UPLOAD,60)
    """
    officer_email = current_user.get("email", "officer")
    return command_service.dispatch_command(
        device_id=cmd_req.device_id,
        command_type=cmd_req.command_type,
        parameters=cmd_req.parameters,
        dispatched_by=officer_email
    )


@router.get("/history", response_model=List[Dict[str, Any]])
def get_command_history(
    device_id: Optional[str] = Query(None, description="Filter by device IMEI"),
    limit: int = Query(50, ge=1, le=10000)
):
    """View forensic command audit trail."""
    return command_service.get_command_history(device_id=device_id, limit=limit)


@router.get("/supported", response_model=Dict[str, str])
def get_supported_commands():
    """List all supported Huaten C05 hardware commands with descriptions."""
    return command_service.get_supported_commands()

