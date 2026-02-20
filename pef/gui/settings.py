"""Settings/preferences management for GUI."""

import logging
import os
import json
from typing import Any, Dict

logger = logging.getLogger(__name__)


class Settings:
    """Manages application settings persistence."""

    DEFAULT_SETTINGS = {
        "last_source_path": "",
        "last_dest_path": "",
        "write_exif": True,
        "window_geometry": "600x400",
    }

    def __init__(self):
        """Initialize settings."""
        self._settings: Dict[str, Any] = self.DEFAULT_SETTINGS.copy()
        self._config_path = self._get_config_path()
        self.load()

    def _get_config_path(self) -> str:
        """Get path to config file."""
        if os.name == "nt":  # Windows
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:  # macOS/Linux
            base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))

        config_dir = os.path.join(base, "pef")
        os.makedirs(config_dir, exist_ok=True)

        return os.path.join(config_dir, "settings.json")

    def load(self):
        """Load settings from file."""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r") as f:
                    loaded = json.load(f)
                    self._settings.update(loaded)
        except Exception as e:
            logger.debug(f"Error loading settings from {self._config_path}: {e}")

    def save(self):
        """Save settings to file."""
        try:
            with open(self._config_path, "w") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            logger.debug(f"Error saving settings to {self._config_path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value."""
        self._settings[key] = value
