# =============================================================================
# styles.py — Dark industrial theme for TCU Controller App
# =============================================================================

DARK = "#0D0D0D"
PANEL = "#141414"
SURFACE = "#1C1C1C"
BORDER = "#2A2A2A"
ACCENT = "#00B4D8"
ACCENT2 = "#0077B6"
GREEN = "#06D6A0"
RED = "#EF476F"
AMBER = "#FFB703"
TEXT = "#E8E8E8"
TEXT_DIM = "#888888"
TEXT_BRIGHT = "#FFFFFF"

APP_STYLE = f"""
QMainWindow, QWidget {{
    background-color: {DARK};
    color: {TEXT};
    font-family: 'Courier New', monospace;
    font-size: 13px;
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {PANEL};
}}

QTabBar::tab {{
    background: {SURFACE};
    color: {TEXT_DIM};
    padding: 10px 28px;
    border: 1px solid {BORDER};
    border-bottom: none;
    font-size: 13px;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

QTabBar::tab:selected {{
    background: {PANEL};
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover {{
    color: {TEXT};
}}

QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 10px 20px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    letter-spacing: 1px;
    text-transform: uppercase;
    min-width: 110px;
    min-height: 38px;
}}

QPushButton:hover {{
    background-color: {BORDER};
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton:pressed {{
    background-color: {ACCENT2};
    color: {TEXT_BRIGHT};
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {SURFACE};
}}

QPushButton#btn_start {{
    background-color: #064e3b;
    border-color: {GREEN};
    color: {GREEN};
}}
QPushButton#btn_start:hover {{
    background-color: #065f46;
}}

QPushButton#btn_stop {{
    background-color: #4c0519;
    border-color: {RED};
    color: {RED};
}}
QPushButton#btn_stop:hover {{
    background-color: #881337;
}}

QPushButton#btn_fill {{
    background-color: #1e3a5f;
    border-color: {ACCENT};
    color: {ACCENT};
}}

QPushButton#btn_test_start {{
    background-color: #064e3b;
    border-color: {GREEN};
    color: {GREEN};
    font-size: 14px;
    min-height: 48px;
    letter-spacing: 2px;
}}

QPushButton#btn_test_stop {{
    background-color: #4c0519;
    border-color: {RED};
    color: {RED};
    font-size: 14px;
    min-height: 48px;
}}

QGroupBox {{
    border: 1px solid {BORDER};
    margin-top: 12px;
    padding: 8px;
    font-size: 11px;
    color: {TEXT_DIM};
    letter-spacing: 2px;
    text-transform: uppercase;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {TEXT_DIM};
}}

QLineEdit, QDoubleSpinBox, QSpinBox {{
    background-color: {SURFACE};
    color: {TEXT_BRIGHT};
    border: 1px solid {BORDER};
    padding: 6px 10px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
}}

QLineEdit:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}

QTextEdit {{
    background-color: {SURFACE};
    color: #88cc88;
    border: 1px solid {BORDER};
    font-family: 'Courier New', monospace;
    font-size: 11px;
    padding: 4px;
}}

QLabel#val_large {{
    font-size: 36px;
    font-family: 'Courier New', monospace;
    color: {ACCENT};
    letter-spacing: 2px;
}}

QLabel#val_medium {{
    font-size: 22px;
    font-family: 'Courier New', monospace;
    color: {TEXT_BRIGHT};
}}

QLabel#status_ok {{
    color: {GREEN};
    font-size: 13px;
    letter-spacing: 1px;
}}

QLabel#status_warn {{
    color: {AMBER};
    font-size: 13px;
    letter-spacing: 1px;
}}

QLabel#status_err {{
    color: {RED};
    font-size: 13px;
    letter-spacing: 1px;
}}

QLabel#label_dim {{
    color: {TEXT_DIM};
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

QScrollBar:vertical {{
    background: {SURFACE};
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 20px;
}}

QProgressBar {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
}}
"""
