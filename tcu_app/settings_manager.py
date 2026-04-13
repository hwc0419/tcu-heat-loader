# =============================================================================
# settings_manager.py — Persistent Settings Manager
# =============================================================================
# Loads and saves user settings to settings.json in the project root.
# Provides defaults for all settings.
# All other modules should read live settings from SettingsManager instance,
# not directly from config.py, so hot reload works correctly.
# =============================================================================

import json
import os
import sys

SETTINGS_FILE = 'settings.json'

# Platform detection
WINDOWS = sys.platform == 'win32'

DEFAULTS = {
    # Serial ports
    'tcu_port':         'COM5'         if WINDOWS else '/dev/ttyUSB0',
    'tcu_baud':         2400,
    'pzem_port':        'COM6'         if WINDOWS else '/dev/ttyAMA0',
    'pzem_baud':        9600,

    # Test parameters
    'temp_setpoint':    22.0,
    'temp_tolerance':   0.5,
    'test_duration':    180,
    'poll_interval':    5,

    # UI preferences
    'theme':            'light',        # 'light' or 'dark'
    'language':         'en',           # 'en', 'zh', 'ms'
}


class SettingsManager:
    """
    Loads settings from settings.json on startup.
    Falls back to DEFAULTS for any missing key.
    Saves to settings.json on every change.

    Usage:
        from settings_manager import settings
        port = settings.get('tcu_port')
        settings.set('theme', 'dark')
    """

    def __init__(self):
        self._data = dict(DEFAULTS)
        self._callbacks = []   # list of callables notified on any change
        self._load()

    def _load(self):
        """Load settings.json — merge with defaults so new keys always exist."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception as e:
                print(f"Settings: could not load {SETTINGS_FILE}: {e} — using defaults")

    def _save(self):
        """Write current settings to settings.json."""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Settings: could not save {SETTINGS_FILE}: {e}")

    def get(self, key, fallback=None):
        """Return a setting value. Falls back to DEFAULTS then fallback."""
        return self._data.get(key, DEFAULTS.get(key, fallback))

    def set(self, key, value):
        """Update a setting, save to disk and notify all callbacks."""
        self._data[key] = value
        self._save()
        for cb in self._callbacks:
            try:
                cb(key, value)
            except Exception as e:
                print(f"Settings callback error: {e}")

    def register_callback(self, fn):
        """Register a callable(key, value) called whenever any setting changes."""
        self._callbacks.append(fn)

    def all(self):
        """Return a copy of all current settings."""
        return dict(self._data)


# ── Module-level singleton — import this everywhere ───────────────────────────
settings = SettingsManager()
