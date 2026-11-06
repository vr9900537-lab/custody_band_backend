"""
Application Configuration Module
Loads settings from environment variables and .env file.
"""

import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

try:
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        ENVIRONMENT: str = "development"
        PROJECT_NAME: str = "Custody Watch Platform"
        API_V1_STR: str = "/api/v1"

        # HTTP API
        API_HOST: str = "0.0.0.0"
        API_PORT: int = 8000

        # TCP/UDP Watch Receiver
        TCP_HOST: str = "0.0.0.0"
        TCP_PORT: int = 9001
        PUBLIC_SERVER_IP: str = "103.44.0.5"

        # Security
        SECRET_KEY: str = "antigravity_custody_watch_super_secret_jwt_key_2026"
        ALGORITHM: str = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

        # Firebase
        FIREBASE_PROJECT_ID: str = "custody-band-a8f59"
        FIREBASE_CREDENTIALS_PATH: str = "secrets/firebase_service_account.json"

        # Admin User
        ADMIN_EMAIL: str = "awsdevopskumar2026@gmail.com"
        ADMIN_NAME: str = "aditya"
        ADMIN_ROLE: str = "admin"
        ADMIN_PASSWORD: str = "Admin@123"

        # Watch defaults
        DEFAULT_MANUFACTURER: str = "MNYD"
        DEFAULT_WATCH_IMEI: str = "863758061830955"
        DEFAULT_WATCH_BATTERY: int = 90
        AUTO_POLL_GPS_ON_PING: bool = True

        model_config = {
            "env_file": str(ENV_FILE),
            "env_file_encoding": "utf-8",
            "extra": "ignore"
        }

    settings = Settings()

except ImportError:
    # Graceful fallback without pydantic-settings
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)

    class SettingsFallback:
        ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Custody Watch Platform")
        API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

        API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
        API_PORT: int = int(os.getenv("API_PORT", 8000))

        TCP_HOST: str = os.getenv("TCP_HOST", "0.0.0.0")
        TCP_PORT: int = int(os.getenv("TCP_PORT", 9001))
        PUBLIC_SERVER_IP: str = os.getenv("PUBLIC_SERVER_IP", "103.44.0.5")

        SECRET_KEY: str = os.getenv("SECRET_KEY", "antigravity_custody_watch_super_secret_jwt_key_2026")
        ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
        ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

        FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "update-custody-band-back-1c169")
        FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "secrets/firebase_service_account.json")

        ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "awsdevopskumar2026@gmail.com")
        ADMIN_NAME: str = os.getenv("ADMIN_NAME", "aditya")
        ADMIN_ROLE: str = os.getenv("ADMIN_ROLE", "admin")
        ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "Admin@123")

        DEFAULT_MANUFACTURER: str = os.getenv("DEFAULT_MANUFACTURER", "MNYD")
        DEFAULT_WATCH_IMEI: str = os.getenv("DEFAULT_WATCH_IMEI", "863758061830955")
        AUTO_POLL_GPS_ON_PING: bool = os.getenv("AUTO_POLL_GPS_ON_PING", "true").lower() == "true"

    settings = SettingsFallback()
