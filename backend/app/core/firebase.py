"""
Firebase Admin, Firestore & Auth Initialization
Connects to Google Cloud Firestore and Firebase Auth using service account credentials.
"""

from pathlib import Path
from typing import Optional
from ..config import settings
from ..utils.logger import app_logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
KEY_PATH = BASE_DIR / settings.FIREBASE_CREDENTIALS_PATH

_firestore_client = None
_firebase_auth = None
_firebase_initialized = False


def init_firebase():
    """Initializes Firebase Admin SDK if service account json exists."""
    global _firestore_client, _firebase_auth, _firebase_initialized

    if _firebase_initialized:
        return _firestore_client

    if KEY_PATH.exists() and KEY_PATH.is_file():
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore, auth

            if not firebase_admin._apps:
                cred = credentials.Certificate(str(KEY_PATH))
                # Automatically use the project matching the certificate credentials
                actual_project_id = getattr(cred, "project_id", None) or settings.FIREBASE_PROJECT_ID
                firebase_admin.initialize_app(cred, {
                    "projectId": actual_project_id
                })

            _firestore_client = firestore.client()
            _firebase_auth = auth
            _firebase_initialized = True
            app_logger.info(f"Connected to Firebase Project '{actual_project_id}' via '{KEY_PATH.name}'")
        except Exception as e:
            app_logger.warning(f"Firebase initialization failed: {e}. Running in local storage mode.")
            _firestore_client = None
            _firebase_auth = None
    else:
        app_logger.info(
            f"Firebase service account not found at '{KEY_PATH}'. Running in local storage / SQLite fallback mode."
        )
        _firestore_client = None
        _firebase_auth = None

    return _firestore_client


def get_firestore_client():
    """Returns the Firestore client, initializing if needed."""
    global _firestore_client
    if _firestore_client is None:
        init_firebase()
    return _firestore_client


def get_firebase_auth():
    """Returns the Firebase Auth module, initializing if needed."""
    global _firebase_auth
    if _firebase_auth is None:
        init_firebase()
    return _firebase_auth


def is_firebase_active() -> bool:
    """Checks whether Firestore client is actively connected."""
    return get_firestore_client() is not None
