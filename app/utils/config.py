"""
Configuration persistence utility for YDL Studio.
Saves settings to a local JSON file.
"""
import json
import os
import sys
from typing import Any, Dict


def get_config_path() -> str:
    """Get the path for config.json in the user data directory or app root."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "ydl_settings.json")


DEFAULT_CONFIG: Dict[str, Any] = {
    "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
    "browser_cookie": "chrome",
    "theme": "Dark",
    "auto_clipboard": True,
}


def load_config() -> Dict[str, Any]:
    """Load configuration from disk or return defaults."""
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration dictionary to disk."""
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
