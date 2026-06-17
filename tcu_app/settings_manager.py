# =============================================================================
# settings_manager.py — Persistent Settings Manager
# =============================================================================
# Loads and saves user settings to settings.json.
# Falls back to DEFAULTS for any missing key.
# Malay language ('ms') falls back to English ('en').
# =============================================================================

import json
import os
import sys

SETTINGS_FILE = 'settings.json'
WINDOWS = sys.platform == 'win32'

DEFAULTS = {
    # Serial ports
    'tcu_port':         'COM5'              if WINDOWS else '/dev/ttyUSB0',
    'tcu_baud':         2400,
    'pzem_port':        'COM6'              if WINDOWS else '/dev/pzem',
    'pzem_baud':        9600,

    # Post-repair test parameters
    'temp_setpoint':    22.0,
    'temp_tolerance':   0.5,
    'flow_setpoint':    50.0,
    'flow_tolerance':   1.5,
    'test_duration':    180,
    'poll_interval':    1,
    'min_flow_rate':    1,
    'flow_fail_grace':  10,

    # UI preferences
    'theme':            'light',
    'language':         'en',           # 'en' or 'zh' only

    # PLC serial port (GPIO UART via MAX3232 → FP0 COM port)
    'plc_port':             'COM7'          if WINDOWS else '/dev/ttyAMA0',

    # Access control (desktop only)
    'rpi_inactivity_timeout_min': 5,
    'access_password_hash': '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
    # ^ SHA-256 of 'admin123' — change via settings Access sub-tab
    'heater_soft_limit_w': 2000,    # admin password required above this (W5 saturation)

    # Stepped heat load test
    'stepped_start_watts':      0,
    'stepped_max_watts':        2000,
    'stepped_step_size_w':      100,
    'stepped_step_duration_s':  300,
    'stepped_rmse_threshold_w': 20.0,

    # AMAT0 stress test
    'stress_test_tolerance':         0.1,    # °C — ± band counted as "in tolerance"
    'stress_test_settle_duration_s': 300,    # consecutive in-tolerance seconds to call it settled
    'stress_test_tail_duration_s':   300,    # seconds logged after each run's own test_end_time
    'stress_test_z_threshold':       2.576,  # |z| above this fails (1% two-tailed default)

    # 2kW heat load sequence test
    'seq_test_load_sequence':      [1000, 1500, 2000, 1500, 1000],  # user-edited stage list
    'seq_test_settle_duration_s':  300,    # consecutive in-tolerance seconds per stage
    'seq_test_tail_duration_s':    300,    # seconds logged after each run's final settle
    'seq_test_z_threshold':        2.576,  # |z| above this fails (1% two-tailed default)
    'seq_test_random_min_w':       1000,   # random sequence generator range
    'seq_test_random_max_w':       2000,
    'seq_test_random_len_min':     10,
    'seq_test_random_len_max':     100,
    'seq_test_history':             [],    # list of {timestamp, sequence} — recallable past runs
}


class SettingsManager:
    """
    Loads settings from settings.json on startup.
    Falls back to DEFAULTS for any missing key.
    Saves to settings.json on every change.
    """

    def __init__(self):
        self._data = dict(DEFAULTS)
        self._callbacks = []
        self._load()

    def _load(self):
        """Load settings.json — merge with defaults so new keys always exist."""
        if not os.path.exists(SETTINGS_FILE):
            return
        try:
            with open(SETTINGS_FILE, 'r') as f:
                saved = json.load(f)
            self._data.update(saved)
            # Migrate: Malay language falls back to English
            if self._data.get('language') == 'ms':
                self._data['language'] = 'en'
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
        if key not in DEFAULTS:
            print(f"Settings: unknown key '{key}' — ignoring")
            return
        self._data[key] = value
        self._save()
        for cb in self._callbacks:
            try:
                cb(key, value)
            except Exception as e:
                print(f"Settings callback error: {e}")

    def register_callback(self, fn):
        """Register a callable(key, value) called on any setting change."""
        self._callbacks.append(fn)

    def all(self):
        """Return a copy of all current settings."""
        return dict(self._data)


# ── Module-level singleton ─────────────────────────────────────────────────────
settings = SettingsManager()
