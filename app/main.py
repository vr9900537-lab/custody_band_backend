import sys
import os
from pathlib import Path
import importlib.util

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
backend_path = str(backend_dir)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
os.environ["PYTHONPATH"] = backend_path + os.pathsep + os.environ.get("PYTHONPATH", "")

# Load real main with package set to 'app'
_real_main = backend_dir / "app" / "main.py"
_spec = importlib.util.spec_from_file_location("app.main", _real_main)
_module = importlib.util.module_from_spec(_spec)
_module.__package__ = "app"
sys.modules["app.main"] = _module
_spec.loader.exec_module(_module)

app = _module.app
lifespan = _module.lifespan

__all__ = ["app", "lifespan"]
