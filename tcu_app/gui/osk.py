# =============================================================================
# osk.py — On-screen keyboard + touch-friendly input widgets
# =============================================================================
# OskLineEdit      → shows Onboard keyboard on tap
# OskSpinBox       → read-only display + tap to open NumpadDialog (integer)
# OskDoubleSpinBox → read-only display + tap to open NumpadDialog (float)
#
# OskSpinBox and OskDoubleSpinBox are drop-in replacements for QSpinBox and
# QDoubleSpinBox. They expose the same API (value(), setValue(), setRange(),
# setSuffix(), setDecimals() etc.) but replace all internal arrow button
# logic with a full-screen numpad dialog on tap.
# =============================================================================

import subprocess
import shutil
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout,
    QLineEdit, QSpinBox, QDoubleSpinBox,
    QDialog, QVBoxLayout, QHBoxLayout as _QHBox,
    QPushButton, QGridLayout, QSizePolicy, QLabel
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class _NumpadLineEdit(QLineEdit):
    """Internal read-only display for OskSpinBox/OskDoubleSpinBox.
    Explicitly blocks Onboard — numpad handles all input."""

    def event(self, event):
        return QLineEdit.event(self, event)  # plain passthrough, no Onboard


_proc           = None
_MAX_DIGITS     = 12    # fixed upper bound on numpad input length


def _show_onboard():
    """Show Onboard — works whether launched at boot or not."""
    # Try dbus first (works if Onboard already running at boot)
    try:
        subprocess.Popen(
            ['dbus-send', '--type=method_call',
             '--dest=org.onboard.Onboard',
             '/org/onboard/Onboard/Keyboard',
             'org.onboard.Onboard.Keyboard.Show'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return
    except Exception:
        pass

    # Fallback — launch Onboard directly if not running
    global _proc
    if _proc is None or _proc.poll() is not None:
        _proc = subprocess.Popen(
            ['onboard', '--size=1200x220'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


# =============================================================================
# NumpadDialog
# =============================================================================

class NumpadDialog(QDialog):
    """Full-screen touch numpad for integer and float input."""

    def __init__(self, title: str, current: str,
                 allow_decimal: bool = False,
                 suffix: str = '', parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(340)
        self._allow_decimal = allow_decimal
        self._suffix        = suffix
        self._build_ui(current)

    def _build_ui(self, current: str):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # Display
        self._display = QLineEdit(current)
        self._display.setReadOnly(True)
        self._display.setAlignment(Qt.AlignRight)
        self._display.setStyleSheet(
            'font-size: 32px; padding: 8px; border: 2px solid #aaa;'
            'border-radius: 6px;')
        root.addWidget(self._display)

        if self._suffix:
            lbl = QLabel(self._suffix)
            lbl.setAlignment(Qt.AlignRight)
            lbl.setStyleSheet('font-size: 14px; color: #888;')
            root.addWidget(lbl)

        # Numpad grid
        grid = QGridLayout()
        grid.setSpacing(10)

        keys = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('0', 3, 0), ('⌫', 3, 2),
        ]
        if self._allow_decimal:
            keys.append(('.', 3, 1))

        for label, row, col in keys:
            btn = QPushButton(label)
            btn.setFixedHeight(72)
            btn.setStyleSheet(
                'font-size: 24px; border-radius: 6px;'
                'background: #2a2a2a; color: white;' if label == '⌫'
                else 'font-size: 24px; border-radius: 6px;')
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _, l=label: self._on_key(l))
            grid.addWidget(btn, row, col)

        root.addLayout(grid)

        # OK / Cancel
        btn_row = _QHBox()
        btn_row.setSpacing(10)
        cancel = QPushButton('Cancel')
        cancel.setFixedHeight(60)
        cancel.setStyleSheet('font-size: 20px; border-radius: 6px;')
        cancel.clicked.connect(self.reject)
        ok = QPushButton('OK')
        ok.setFixedHeight(60)
        ok.setStyleSheet(
            'font-size: 20px; border-radius: 6px;'
            'background: #065f46; color: white;')
        ok.clicked.connect(self.accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        root.addLayout(btn_row)

    def _on_key(self, key: str):
        cur = self._display.text()
        if key == '⌫':
            self._display.setText(cur[:-1] or '0')
        elif key == '.' and '.' in cur:
            return
        elif len(cur.replace('.', '').replace('-', '')) >= _MAX_DIGITS:
            return
        else:
            self._display.setText(key if cur == '0' and key != '.' else cur + key)

    def value(self) -> str:
        return self._display.text()


# =============================================================================
# OskLineEdit
# =============================================================================

class OskLineEdit(QLineEdit):
    """QLineEdit that shows Onboard keyboard on click/tap."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Accept touch events directly — don't rely on mouse synthesis
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)

    def event(self, event):
        """Intercept all events — catches both mouse and touch taps."""
        from PyQt5.QtCore import QEvent
        if event.type() in (
            QEvent.TouchBegin,
            QEvent.MouseButtonPress,
        ):
            _show_onboard()
        return super().event(event)


# =============================================================================
# OskSpinBox — replaces QSpinBox entirely, no arrow buttons
# =============================================================================

class OskSpinBox(QWidget):
    """
    Drop-in QSpinBox replacement.
    Renders as a read-only display field. Tap opens NumpadDialog.
    No arrow buttons. Full QSpinBox API compatibility.
    """

    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value   = 0
        self._min     = 0
        self._max     = 99
        self._step    = 1
        self._suffix  = ''
        self._prefix  = ''
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = _NumpadLineEdit()
        self._edit.setReadOnly(True)
        self._edit.setAlignment(Qt.AlignLeft)
        self._edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._edit.mousePressEvent = lambda e: self._open_numpad()
        self._edit.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self._edit.event = self._intercept_touch
        self._refresh_display()
        layout.addWidget(self._edit)


    def _intercept_touch(self, event):
        """Intercept touch/mouse events on display field → open numpad."""
        from PyQt5.QtCore import QEvent
        if event.type() in (QEvent.TouchBegin, QEvent.MouseButtonPress):
            self._open_numpad()
            return True
        return _NumpadLineEdit.event(self._edit, event)

    def _refresh_display(self):
        self._edit.setText(f'{self._prefix}{self._value}{self._suffix}')

    def _open_numpad(self):
        dlg = NumpadDialog(
            'Enter value', str(self._value),
            allow_decimal=False,
            suffix=self._suffix,
            parent=self
        )
        if dlg.exec_() == QDialog.Accepted:
            try:
                val = int(dlg.value())
                self.setValue(max(self._min, min(self._max, val)))
            except ValueError:
                pass

    # ── QSpinBox API compatibility ────────────────────────────────────────────
    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        v = max(self._min, min(self._max, int(v)))
        if v != self._value:
            self._value = v
            self._refresh_display()
            self.valueChanged.emit(self._value)

    def setRange(self, mn: int, mx: int):
        self._min = int(mn)
        self._max = int(mx)
        self.setValue(self._value)

    def setMinimum(self, mn: int):
        self._min = int(mn)

    def setMaximum(self, mx: int):
        self._max = int(mx)

    def minimum(self) -> int:
        return self._min

    def maximum(self) -> int:
        return self._max

    def setSingleStep(self, s: int):
        self._step = int(s)

    def singleStep(self) -> int:
        return self._step

    def setSuffix(self, s: str):
        self._suffix = s
        self._refresh_display()

    def setPrefix(self, p: str):
        self._prefix = p
        self._refresh_display()

    def setReadOnly(self, _):
        pass  # always read-only — input via numpad only

    def setStyleSheet(self, s: str):
        self._edit.setStyleSheet(s)

    def setFixedWidth(self, w: int):
        self._edit.setFixedWidth(w)

    def setFixedHeight(self, h: int):
        self._edit.setFixedHeight(h)


# =============================================================================
# OskDoubleSpinBox — replaces QDoubleSpinBox entirely, no arrow buttons
# =============================================================================

class OskDoubleSpinBox(QWidget):
    """
    Drop-in QDoubleSpinBox replacement.
    Renders as a read-only display field. Tap opens NumpadDialog.
    No arrow buttons. Full QDoubleSpinBox API compatibility.
    """

    valueChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value    = 0.0
        self._min      = 0.0
        self._max      = 99.0
        self._step     = 1.0
        self._decimals = 2
        self._suffix   = ''
        self._prefix   = ''
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = _NumpadLineEdit()
        self._edit.setReadOnly(True)
        self._edit.setAlignment(Qt.AlignLeft)
        self._edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._edit.mousePressEvent = lambda e: self._open_numpad()
        self._edit.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self._edit.event = self._intercept_touch
        self._refresh_display()
        layout.addWidget(self._edit)


    def _intercept_touch(self, event):
        """Intercept touch/mouse events on display field → open numpad."""
        from PyQt5.QtCore import QEvent
        if event.type() in (QEvent.TouchBegin, QEvent.MouseButtonPress):
            self._open_numpad()
            return True
        return _NumpadLineEdit.event(self._edit, event)

    def _refresh_display(self):
        self._edit.setText(
            f'{self._prefix}{self._value:.{self._decimals}f}{self._suffix}')

    def _open_numpad(self):
        dlg = NumpadDialog(
            'Enter value', f'{self._value:.{self._decimals}f}',
            allow_decimal=True,
            suffix=self._suffix,
            parent=self
        )
        if dlg.exec_() == QDialog.Accepted:
            try:
                val = round(float(dlg.value()), self._decimals)
                self.setValue(max(self._min, min(self._max, val)))
            except ValueError:
                pass

    # ── QDoubleSpinBox API compatibility ──────────────────────────────────────
    def value(self) -> float:
        return self._value

    def setValue(self, v: float):
        v = round(max(self._min, min(self._max, float(v))), self._decimals)
        if v != self._value:
            self._value = v
            self._refresh_display()
            self.valueChanged.emit(self._value)

    def setRange(self, mn: float, mx: float):
        self._min = float(mn)
        self._max = float(mx)
        self.setValue(self._value)

    def setMinimum(self, mn: float):
        self._min = float(mn)

    def setMaximum(self, mx: float):
        self._max = float(mx)

    def minimum(self) -> float:
        return self._min

    def maximum(self) -> float:
        return self._max

    def setSingleStep(self, s: float):
        self._step = float(s)

    def singleStep(self) -> float:
        return self._step

    def setDecimals(self, d: int):
        self._decimals = int(d)
        self._refresh_display()

    def decimals(self) -> int:
        return self._decimals

    def setSuffix(self, s: str):
        self._suffix = s
        self._refresh_display()

    def setPrefix(self, p: str):
        self._prefix = p
        self._refresh_display()

    def setReadOnly(self, _):
        pass  # always read-only — input via numpad only

    def setStyleSheet(self, s: str):
        self._edit.setStyleSheet(s)

    def setFixedWidth(self, w: int):
        self._edit.setFixedWidth(w)

    def setFixedHeight(self, h: int):
        self._edit.setFixedHeight(h)
