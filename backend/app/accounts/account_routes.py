"""
Account API Routes
Endpoints for officer directories, profile management, and account settings.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from ..accounts.account_schemas import AccountResponse, AccountUpdate, PasswordChangeRequest
from ..accounts.account_service import account_service
from ..core.dependencies import get_current_user

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("", response_model=List[Dict[str, Any]])
def list_accounts(current_user: dict = Depends(get_current_user)):
    """List all registered officers and administrators."""
    return account_service.list_accounts()


@router.get("/{email}", response_model=Dict[str, Any])
def get_account(email: str, current_user: dict = Depends(get_current_user)):
    """Get full officer profile details."""
    acc = account_service.get_account(email)
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return acc


@router.put("/{email}", response_model=Dict[str, Any])
def update_account(email: str, update_in: AccountUpdate, current_user: dict = Depends(get_current_user)):
    """Update officer contact info, badge number, or department."""
    return account_service.update_account(email, update_in)


@router.post("/{email}/change-password", response_model=Dict[str, Any])
def change_password(email: str, pw_req: PasswordChangeRequest, current_user: dict = Depends(get_current_user)):
    """Change account password with verification of current password."""
    try:
        success = account_service.change_password(email, pw_req)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        return {"status": "success", "message": "Password updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{email}", response_model=Dict[str, Any])
def deactivate_account(email: str, current_user: dict = Depends(get_current_user)):
    """Deactivate an officer account."""
    success = account_service.deactivate_account(email)
    return {"status": "success", "deactivated": success}

