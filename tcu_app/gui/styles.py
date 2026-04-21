# =============================================================================
# styles.py — Light mode theme for TCU Controller App
# =============================================================================
# All font sizes, paddings and minimum dimensions scale dynamically based on
# the screen resolution detected at startup via get_app_style(scale).
# Call get_app_style(scale) from main_window.py after computing scale factor.
# =============================================================================

# ── Colour palette ────────────────────────────────────────────────────────────
BG         = "#F5F5F5"   # main window background
PANEL      = "#FFFFFF"   # tab content background
SURFACE    = "#EEEEEE"   # widget surfaces (buttons, inputs)
BORDER     = "#CCCCCC"   # borders and dividers
ACCENT     = "#0077B6"   # primary accent — blue
ACCENT2    = "#005F8A"   # darker accent for pressed states
GREEN      = "#1B7F4F"   # pass / start / ok
RED        = "#C0392B"   # fail / stop / error
AMBER      = "#B8860B"   # warning
TEXT       = "#1A1A1A"   # primary text
TEXT_DIM   = "#666666"   # secondary / label text
TEXT_BRIGHT= "#000000"   # maximum contrast text


def get_app_style(scale: float = 1.0, theme: str = None) -> str:
    """
    Generate the full application stylesheet scaled to the current display.
    theme: 'light' or 'dark' — defaults to settings_manager value if None.
    """
    if theme is None:
        try:
            from settings_manager import settings
            theme = settings.get('theme', 'light')
        except Exception:
            theme = 'light'

    if theme == 'dark':
        bg      = "#0D0D0D"
        panel   = "#141414"
        surface = "#1C1C1C"
        border  = "#2A2A2A"
        accent  = "#00B4D8"
        accent2 = "#0077B6"
        green   = "#06D6A0"
        red     = "#EF476F"
        amber   = "#FFB703"
        text    = "#E8E8E8"
        tdim    = "#888888"
        tbright = "#FFFFFF"
        graph_bg       = "'k'"
        log_color      = "#88cc88"
        btn_start_bg   = "#064e3b"
        btn_start_hov  = "#065f46"
        btn_stop_bg    = "#4c0519"
        btn_stop_hov   = "#881337"
        btn_fill_bg    = "#1e3a5f"
        btn_tstart_bg  = "#064e3b"
        btn_tstop_bg   = "#4c0519"
        header_bg      = "#0A0A0A"
        header_border  = "#2A2A2A"
    else:
        # Light mode
        bg      = "#F5F5F5"
        panel   = "#FFFFFF"
        surface = "#EEEEEE"
        border  = "#CCCCCC"
        accent  = "#0077B6"
        accent2 = "#005F8A"
        green   = "#1B7F4F"
        red     = "#C0392B"
        amber   = "#B8860B"
        text    = "#1A1A1A"
        tdim    = "#666666"
        tbright = "#000000"
        log_color      = "#1A5E20"
        btn_start_bg   = "#D4EDDA"
        btn_start_hov  = "#C3E6CB"
        btn_stop_bg    = "#F8D7DA"
        btn_stop_hov   = "#F5C6CB"
        btn_fill_bg    = "#D0EAF5"
        btn_tstart_bg  = "#D4EDDA"
        btn_tstop_bg   = "#F8D7DA"
        header_bg      = "#E0E0E0"
        header_border  = "#CCCCCC"

    def px(base: int) -> str:
        return f"{max(1, round(base * scale))}px"

    def pt(base: int) -> str:
        return f"{max(8, round(base * scale))}px"

    return f"""
QMainWindow, QWidget {{
    background-color: {bg};
    color: {text};
    font-family: 'Courier New', monospace;
    font-size: {pt(13)};
}}

QTabWidget::pane {{
    border: 1px solid {border};
    background: {panel};
}}

QTabBar::tab {{
    background: {surface};
    color: {tdim};
    padding: {px(6)} {px(10)};
    border: 1px solid {border};
    border-bottom: none;
    font-size: {pt(11)};
    letter-spacing: 0px;
    text-transform: uppercase;
}}

QTabBar::tab:selected {{
    background: {panel};
    color: {accent};
    border-bottom: 2px solid {accent};
}}

QTabBar::tab:hover {{
    color: {text};
    background: {panel};
}}

QPushButton {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    padding: {px(8)} {px(14)};
    font-family: 'Courier New', monospace;
    font-size: {pt(11)};
    letter-spacing: {px(1)};
    text-transform: uppercase;
    min-width: {px(90)};
    min-height: {px(32)};
}}

QPushButton:hover {{
    background-color: {border};
    border-color: {accent};
    color: {accent};
}}

QPushButton:pressed {{
    background-color: {accent2};
    color: {panel};
}}

QPushButton:disabled {{
    color: {border};
    border-color: {surface};
}}

QPushButton#btn_start {{
    background-color: {btn_start_bg};
    border-color: {green};
    color: {green};
}}
QPushButton#btn_start:hover {{
    background-color: {btn_start_hov};
}}

QPushButton#btn_stop {{
    background-color: {btn_stop_bg};
    border-color: {red};
    color: {red};
}}
QPushButton#btn_stop:hover {{
    background-color: {btn_stop_hov};
}}

QPushButton#btn_estop {{
    background-color: #B91C1C;
    border: 2px solid #7F1D1D;
    border-radius: 8px;
    color: #FFFFFF;
    font-size: {pt(10)};
    font-weight: bold;
    letter-spacing: {px(1)};
}}
QPushButton#btn_estop:hover {{
    background-color: #DC2626;
}}
QPushButton#btn_estop:pressed {{
    background-color: #991B1B;
}}

QPushButton#btn_fill {{
    background-color: {btn_fill_bg};
    border-color: {accent};
    color: {accent};
}}

QPushButton#btn_test_start {{
    background-color: {btn_tstart_bg};
    border-color: {green};
    color: {green};
    font-size: {pt(13)};
    min-height: {px(42)};
    letter-spacing: {px(1)};
}}

QPushButton#btn_test_stop {{
    background-color: {btn_tstop_bg};
    border-color: {red};
    color: {red};
    font-size: {pt(13)};
    min-height: {px(42)};
}}

QGroupBox {{
    border: 1px solid {border};
    margin-top: {px(10)};
    padding: {px(6)};
    font-size: {pt(10)};
    color: {tdim};
    letter-spacing: {px(1)};
    text-transform: uppercase;
    background-color: {panel};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: {px(8)};
    padding: 0 {px(4)};
    color: {tdim};
    background-color: {panel};
}}

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background-color: {panel};
    color: {tbright};
    border: 1px solid {border};
    padding: {px(5)} {px(8)};
    font-family: 'Courier New', monospace;
    font-size: {pt(12)};
}}

QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {accent};
}}

QComboBox::drop-down {{
    border: none;
    width: {px(20)};
}}

QTextEdit {{
    background-color: {panel};
    color: {log_color};
    border: 1px solid {border};
    font-family: 'Courier New', monospace;
    font-size: {pt(10)};
    padding: {px(3)};
}}

QLabel#val_large {{
    font-size: {pt(30)};
    font-family: 'Courier New', monospace;
    color: {accent};
    letter-spacing: {px(1)};
}}

QLabel#val_medium {{
    font-size: {pt(18)};
    font-family: 'Courier New', monospace;
    color: {tbright};
}}

QLabel#status_ok {{
    color: {green};
    font-size: {pt(12)};
    letter-spacing: {px(1)};
}}

QLabel#status_warn {{
    color: {amber};
    font-size: {pt(12)};
    letter-spacing: {px(1)};
}}

QLabel#status_err {{
    color: {red};
    font-size: {pt(12)};
    letter-spacing: {px(1)};
}}

QLabel#label_dim {{
    color: {tdim};
    font-size: {pt(10)};
    letter-spacing: {px(1)};
    text-transform: uppercase;
}}

QScrollBar:vertical {{
    background: {surface};
    width: {px(8)};
}}
QScrollBar::handle:vertical {{
    background: {border};
    min-height: {px(20)};
}}

QProgressBar {{
    background-color: {surface};
    border: 1px solid {border};
    height: {px(8)};
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {accent};
}}

QStatusBar {{
    background-color: {surface};
    color: {tdim};
    border-top: 1px solid {border};
}}
"""


# Legacy constant — kept for any direct imports elsewhere
APP_STYLE = get_app_style(1.0)


# ── Convenience constants for direct import by tabs ───────────────────────────
# These reflect the LIGHT theme defaults.
# For dark theme, the stylesheet overrides these via QSS.
PANEL    = "#FFFFFF"
SURFACE  = "#EEEEEE"
BORDER   = "#CCCCCC"
ACCENT   = "#0077B6"
GREEN    = "#1B7F4F"
RED      = "#C0392B"
AMBER    = "#B8860B"
TEXT     = "#1A1A1A"
TEXT_DIM = "#666666"
