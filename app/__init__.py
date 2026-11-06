import sys
import os
from pathlib import Path

# Add backend directory to sys.path so all imports inside backend resolve seamlessly
backend_dir = Path(__file__).resolve().parent.parent / "backend"
backend_path = str(backend_dir)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
os.environ["PYTHONPATH"] = backend_path + os.pathsep + os.environ.get("PYTHONPATH", "")

# Extend package search path to include backend/app
backend_app_dir = backend_dir / "app"
if backend_app_dir.exists():
    __path__.append(str(backend_app_dir))

