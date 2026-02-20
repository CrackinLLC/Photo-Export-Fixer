"""Tests for GUI components (non-interactive logic)."""

import os
from unittest.mock import patch

from pef.gui.settings import Settings


class TestSettingsXDGConfigHome:
    """Tests for XDG_CONFIG_HOME support in Settings."""

    @patch("os.name", "posix")
    @patch("os.makedirs")
    def test_xdg_config_home_used_on_linux(self, mock_makedirs):
        """XDG_CONFIG_HOME is respected on non-Windows platforms."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}, clear=False):
            settings = Settings.__new__(Settings)
            path = settings._get_config_path()
            assert path == os.path.join("/custom/config", "pef", "settings.json")

    @patch("os.name", "posix")
    @patch("os.makedirs")
    def test_xdg_falls_back_to_dot_config(self, mock_makedirs):
        """Falls back to ~/.config when XDG_CONFIG_HOME is not set."""
        env = os.environ.copy()
        env.pop("XDG_CONFIG_HOME", None)
        with patch.dict(os.environ, env, clear=True):
            settings = Settings.__new__(Settings)
            path = settings._get_config_path()
            expected = os.path.join(os.path.expanduser("~/.config"), "pef", "settings.json")
            assert path == expected

    @patch("os.name", "nt")
    @patch("os.makedirs")
    def test_windows_ignores_xdg(self, mock_makedirs):
        """Windows uses APPDATA, not XDG_CONFIG_HOME."""
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config", "APPDATA": "C:\\Users\\test\\AppData\\Roaming"}, clear=False):
            settings = Settings.__new__(Settings)
            path = settings._get_config_path()
            assert "pef" in path
            assert "/custom/config" not in path
