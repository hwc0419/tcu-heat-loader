# TCU++ — Heat Load Simulator

> SSMC Semiconductor Manufacturing · Howard (CE Student Intern) · 2026

A Raspberry Pi 4 based heat load simulator for post-repair qualification of Haake ASM Temperature Control Units (TCUs). Replaces a USD 19,800 vendor solution at under USD 600.

---

## Overview

ASML photo tools (scanners) in the fab are cooled by Haake ASM TCUs maintained at 22°C. When a TCU is sent for repair, the current post-repair test does not simulate the real heat load from the photo tool — a repaired TCU can pass the bare test and then fail in production.

This project improves an existing in-house heat loader jig with a Raspberry Pi 4 running a PyQt5 monitoring and control application (TCU++), a PZEM-004T energy meter for true watts measurement, and a web dashboard accessible from any phone on the workshop network.

---

## Hardware

| Component | Model | Notes |
|-----------|-------|-------|
| RPi 4 | 4GB, 64GB SD | Production controller |
| Touchscreen | Waveshare 15.6" HDMI LCD (H) | `hdmi_mode=82` in config.txt |
| TCU | Haake ASM 1kW | RS232 DB9, 2400 baud 8N1 |
| PLC | Panasonic FP0-C14CRS | Standalone — no runtime serial |
| HMI | Panasonic GT02 | 500W / 1000W / 2000W stage select |
| Power regulator | HoTTemP W5SP4V030-24J | 0–5VDC input, phase angle SCR |
| Heater | Reach Electrical 262627 | 2kW — delivers ~1400W at 2000W stage |
| Contactor | Schneider TeSys | Driven by FP0 Y0 |
| PSU | Mean Well LRS-100-24 | 24VDC for PLC and HMI |
| Energy meter | PZEM-004T v3.0 + 100A CT | GPIO UART — `/dev/ttyAMA0` |
| RCCB | 2P 40A 30mA AC | CP5 compliance |

### RS232 Connection (TCU)

```
TCU DB25 → FTDI DT5011 USB-RS232 adapter → RPi USB
Port: /dev/ttyUSB0 (Linux) | COM5 (Windows)
Settings: 2400 baud, 8N1, no handshake
Cable: straight-through DB9 F-F (NOT crossover)
```

### PZEM-004T GPIO UART Wiring

```
PZEM TX → RPi pin 10 (GPIO15 RX)
PZEM RX → RPi pin 8  (GPIO14 TX)
PZEM 5V → RPi pin 2
PZEM GND → RPi pin 6
```

RPi UART setup (run once):
```bash
sudo raspi-config  # Interface Options → Serial Port → shell: No, hardware: Yes
# Add to /boot/firmware/config.txt:
dtoverlay=disable-bt
sudo reboot
```

---

## Software Architecture

```
tcu_app/
├── main.py                  Entry point
├── config.py                Hard constants — all referenced by name
├── settings_manager.py      settings.json loader — singleton
├── tcu.py                   Haake TCU RS232 (class TCU)
├── heater.py                Modbus RTU heater controller (class Heater)
├── pzem004t.py              PZEM-004T energy meter Modbus RTU
├── daq_thread.py            1Hz DAQ thread — Sample dataclass
├── logger_thread.py         CSV logger thread — decoupled from DAQ
├── test_logic.py            Pass/fail logic, alarm parsing, BS decode
├── ipc.py                   IPC abstraction — JSON (Windows) / socket (Linux)
├── audit_logger.py          Operator action audit trail
├── translations.py          EN/ZH string dict — tr(key)
├── web_server.py            Flask web dashboard backend
├── generate_vapid.py        Run once — generates VAPID push keys
└── gui/
    ├── main_window.py       Top-level QMainWindow
    ├── monitor_tab.py       Live TCU readings + graph
    ├── test_tab.py          180-min heat load pass/fail test
    ├── heater_tab.py        Heater control (Modbus setpoint + live graph)
    ├── response_test_tab.py Step response test — settling time detection
    ├── settings_tab.py      5 sub-tabs: Serial, Test, Heater, Response, Display
    ├── docs_tab.py          Built-in documentation — 6 sub-tabs
    ├── osk.py               On-screen keyboard — text fields + numpad
    ├── graph_utils.py       Shared graph helpers — popup + export
    └── styles.py            Light/dark theme — dynamic scaling
```

### Thread Model

```
Main (GUI) thread
    │
    ├── DAQThread (daemon)        — polls TCU + PZEM at configurable interval
    │       │                       writes to ui_queue (maxsize=1) and log_queue
    │       └── IPCWriter         — serves latest sample to web server
    │
    ├── LoggerThread (daemon)     — consumes log_queue, writes CSV rows
    │
    └── Qt timer (16ms)           — drains ui_queue, emits new_sample signal
```

No GUI code ever touches the serial port. No DAQ code ever touches Qt widgets. The queues are the only crossing point.

### Key Design Decisions

| Topic | Decision |
|-------|----------|
| IPC | JSON file on Windows, Unix socket on Linux — `sys.platform` auto-selects |
| Flow rate | Parsed as `float` not `int` from TCU D command |
| PZEM registers | Integer scaled (÷10, ÷1000) — NOT IEEE 754 floats |
| BS healthy state | `0x400400` — b2 bit 2 = main contactor ON (normal running) |
| Flow fail grace | 5 consecutive low readings before FAIL (~5s at 1Hz) |
| Temp tolerance | 0.5°C (manager requirement) |
| Test duration | 180 min (manager requirement) |
| UI scaling | `scale = screen.width()/1920` clamped 0.65–1.0 |
| OSK | Keyboard on text fields, numpad on spinboxes — RPi touchscreen |

---

## Installation

### RPi (production)

```bash
git clone https://github.com/hwc0419/tcu-heat-loader.git
cd tcu-heat-loader/tcu_app
pip3 install -r requirements.txt --break-system-packages
```

### Windows (development/testing)

```bash
git clone https://github.com/hwc0419/tcu-heat-loader.git
cd tcu-heat-loader/tcu_app
pip install -r requirements.txt
python main.py
```

Platform (port names, IPC method) is auto-detected via `sys.platform`.

### Auto-start on Boot (RPi)

```bash
sudo cp tcu-app.service /etc/systemd/system/
sudo cp tcu-web.service /etc/systemd/system/
sudo systemctl enable tcu-app tcu-web
sudo systemctl start  tcu-app tcu-web
```

Both services have `Restart=always` — auto-restart on crash.

---

## Running

```bash
cd tcu_app

# Desktop app only
python3 main.py

# Desktop app + web dashboard (two terminals)
python3 main.py
python3 web_server.py
```

Web dashboard: `http://tcuplusplus.local:5000`

---

## Web Dashboard

Browser-based PWA. No installation needed — works on any phone or laptop on workshop WiFi.

### First-time Setup

```bash
# Generate VAPID keys for push notifications (run once)
python3 generate_vapid.py

# Set up mDNS hostname
sudo apt install avahi-daemon
sudo hostnamectl set-hostname tcuplusplus
sudo reboot
```

### User Management

Users stored in `tcu_app/users.json` (SHA-256 hashed passwords, gitignored).

```python
import hashlib, json
with open('tcu_app/users.json') as f:
    users = json.load(f)
users['newuser'] = {
    'password': hashlib.sha256('password'.encode()).hexdigest(),
    'role': 'technician',   # or 'supervisor'
    'name': 'New User'
}
with open('tcu_app/users.json', 'w') as f:
    json.dump(users, f, indent=2)
```

Roles: `technician` (full control) / `supervisor` (view only).

Operator lock: one technician at a time, FIFO queue, 5-min inactivity timeout. Physical touchscreen always overrides web operators.

---

## Pass/Fail Criteria (180-min Heat Load Test)

| Criterion | Threshold |
|-----------|-----------|
| Inlet temperature | 22.0°C ± 0.5°C for full 180 min |
| Flow rate | ≥ 1 ℓ/min continuously (5s grace on transient drops) |
| TCU alarms | None (BS = 0x400400) |
| Duration | 180 min completed without abort |

CSV logs saved to `tcu_app/logs/` — filename includes TCU serial and timestamp.

---

## PLC Summary (FP0-C14CRS)

The existing jig PLC operates standalone at runtime — no serial communication with the RPi.

| Output | Function |
|--------|----------|
| Y0 | Schneider TeSys contactor coil — main heater enable |
| Y4 | W5 SCR run enable |
| WY4 | W5 analogue setpoint — 0–4000 counts = 0–5V = 0–100% |

| Input | Function |
|-------|----------|
| X5 | Safety trip — kills contactor + W5 immediately (E-stop / RCCB) |
| X0 | Heater enable gate |
| X2 | Heater inhibit |
| WX2 | Analogue setpoint from GT02 HMI |

W5 stages: K500 (→ ~265W actual) / K1000 (→ ~616W) / K2000 (→ ~1400W). VR3 deliberately capped at 70% rated capacity for thermal derating in enclosed panel.

Full PLC analysis: see Section 11 of `docs/TCU_Project_Context_v2.docx`.

---

## Milestones

| Milestone | Status |
|-----------|--------|
| M1 — Core TCU++ app | ✅ Complete |
| M2 — Quality of life (web dashboard, settings, i18n) | ✅ Complete |
| M3 — Hardware integration (PZEM, RCCB, jig calibration) | ⚠️ In progress |
| M4 — BIBO stability qualification | ❌ Not started |

### M3 Remaining

- PZEM-004T wiring (electrician — tap L/N from W5 output, clip CT)
- RCCB installation (electrician)
- RPi touchscreen workshop setup
- SD card IT policy exception
- IoTConnect router access

### M4 — BIBO Proof

Target theorem: `∃ T_transient: |h(t) - 22°C| ≤ 0.5°C for all t > T_transient` for any `Q_waste(t) ∈ [Q_min, Q_max]`.

Requires M3 completion + 3hr step response tests at each heat load stage.

---

## Repository Structure

```
tcu-heat-loader/
├── tcu_app/          PyQt5 application (RPi production)
├── web/              Phone web app (HTML/JS/CSS)
├── docs/             BOM, manuals, project context document
└── README.md
```

Gitignored: `logs/`, `settings.json`, `users.json`, `vapid_keys.json`, `.tcu_ipc.json`, `.tcu_cmd.json`

---

## Budget

| Item | SGD |
|------|-----|
| Raspberry Pi 4 4GB | 102.40 |
| RPi case + fan | 6.27 |
| Official RPi USB-C PSU | 18.58 |
| 15.6" HDMI touchscreen | 235.00 |
| FTDI USB-RS232 adapter | 25.00 |
| Panasonic AFC8503 PLC cable | 81.10 |
| PZEM-004T + 100A CT | 45.00 |
| RCCB 2P 40A 30mA | 55.90 |
| **Total** | **569.25** |

Existing jig hardware (PLC, HMI, heater, W5, contactor, panel): SGD 0 (in-house assets).

Vendor quote for equivalent solution: USD 19,800.
