import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def load_settings(custom_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Loads settings JSON from either:
    - A custom path if provided and exists, or
    - src/config/settings.json if it exists, otherwise