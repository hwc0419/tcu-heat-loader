# =============================================================================
# graph_utils.py — Shared graph utilities
# =============================================================================
# Provides:
#   make_graph_panel(title, scale)  → (container, plot_widget, export_btn)
#   apply_graph_style(plot_widget, ...)
#   export_graph(plot_widget, stem)
#
# Every panel created by make_graph_panel automatically gets:
#   • Auto Fit button  — resets view to fit all data
#   • Add Line button  — opens dialog; user picks H/V, style, colour,
#                        then drags the resulting InfiniteLine to position
#   • Clear Lines btn  — removes all annotation lines at once
#   • Delete on click  — click a line to select it, then press Delete
# =============================================================================

import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSizePolicy,
    QDialog, QDialogButtonBox, QComboBox, QFormLayout,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QFont, QKeyEvent
import pyqtgraph as pg
import pyqtgraph.exporters as pgexp

from gui.styles import (
    GRAPH_BG, GRAPH_TEMP_COLOR, GRAPH_FLOW_COLOR,
    GRAPH_AXIS_FONT_SIZE_PX, TEXT, TEXT_DIM,
    GRAPH_LINE_COLORS,
)

_MAX_FILTER_LEN  = 2          # PNG + SVG export options
_MAX_ANNO_LINES  = 20         # hard upper bound on annotation lines per graph
_AXIS_FONT       = QFont('Courier New', GRAPH_AXIS_FONT_SIZE_PX)

_STYLE_MAP = {
    'Solid':  Qt.SolidLine,
    'Dashed': Qt.DashLine,
    'Dotted': Qt.DotLine,
}


# =============================================================================
# _AddLineDialog — modal dialog for axis / style / colour selection
# =============================================================================

class _AddLineDialog(QDialog):
    """Small modal dialog: axis (H/V), line style, colour."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Annotation Line')
        self.setModal(True)

        form = QFormLayout(self)

        self._axis_cb = QComboBox()
        self._axis_cb.addItems(['Horizontal (Y)', 'Vertical (X)'])
        form.addRow('Axis:', self._axis_cb)

        self._style_cb = QComboBox()
        self._style_cb.addItems(list(_STYLE_MAP.keys()))   # Solid / Dashed / Dotted
        form.addRow('Style:', self._style_cb)

        self._color_cb = QComboBox()
        for name in GRAPH_LINE_COLORS:
            self._color_cb.addItem(name)
        form.addRow('Colour:', self._color_cb)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self):
        """Return (angle, qt_line_style, hex_color)."""
        angle  = 0 if self._axis_cb.currentIndex() == 0 else 90
        style  = _STYLE_MAP[self._style_cb.currentText()]
        color  = GRAPH_LINE_COLORS[self._color_cb.currentText()]
        return angle, style, color


# =============================================================================
# _LineManager — owns annotation lines for one PlotWidget
# =============================================================================

class _LineManager(QObject):
    """
    Manages draggable annotation InfiniteLine items for a single PlotWidget.

    • add_line(angle, style, color) — adds a movable line at the current
      centre of the view; user then drags it into place.
    • clear_lines()                 — removes all annotation lines.
    • on_key_delete()               — removes the currently selected line.

    Lines are stored in self._lines (list, max _MAX_ANNO_LINES).
    The selected line (last clicked) is stored in self._selected.
    """

    def __init__(self, plot_widget: pg.PlotWidget, parent=None):
        super().__init__(parent)
        self._plot     = plot_widget
        self._lines    = []          # list[pg.InfiniteLine]
        self._selected = None        # currently selected line

        # Install key event filter on the plot viewport so Delete works
        self._plot.viewport().installEventFilter(self)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_line(self, angle: int, style: Qt.PenStyle, color: str):
        """Add one draggable annotation line at the centre of the current view."""
        if len(self._lines) >= _MAX_ANNO_LINES:
            return

        pi      = self._plot.getPlotItem()
        vb      = pi.getViewBox()
        x_range, y_range = vb.viewRange()

        if angle == 0:   # horizontal — position at Y midpoint
            pos = (y_range[0] + y_range[1]) / 2.0
        else:            # vertical — position at X midpoint
            pos = (x_range[0] + x_range[1]) / 2.0

        pen  = pg.mkPen(color=color, width=2, style=style)
        line = pg.InfiniteLine(
            pos=pos, angle=angle,
            pen=pen, movable=True,
            hoverPen=pg.mkPen(color=color, width=3, style=style),
        )
        line.sigClicked.connect(self._on_line_clicked)
        self._plot.addItem(line)
        self._lines.append(line)
        self._select(line)

    def clear_lines(self):
        """Remove all annotation lines from the graph."""
        for i in range(len(self._lines)):
            self._plot.removeItem(self._lines[i])
        self._lines.clear()
        self._selected = None

    def on_key_delete(self):
        """Remove the currently selected line (if any)."""
        if self._selected is None:
            return
        if self._selected not in self._lines:
            self._selected = None
            return
        self._plot.removeItem(self._selected)
        self._lines.remove(self._selected)
        self._selected = None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _select(self, line: pg.InfiniteLine):
        """Highlight the selected line; de-highlight the previous one."""
        if self._selected is not None and self._selected in self._lines:
            old_pen = self._selected.pen
            dim_pen = pg.mkPen(color=old_pen.color(), width=2,
                               style=old_pen.style())
            self._selected.setPen(dim_pen)
        self._selected = line
        sel_pen = pg.mkPen(color=line.pen.color(), width=4,
                           style=line.pen.style())
        line.setPen(sel_pen)

    def _on_line_clicked(self, line, _ev):
        self._select(line)

    def eventFilter(self, obj, event):
        """Intercept Delete key press on the plot viewport."""
        if (obj is self._plot.viewport()
                and isinstance(event, QKeyEvent)
                and event.type() == QKeyEvent.KeyPress
                and event.key() in (Qt.Key_Delete, Qt.Key_Backspace)):
            self.on_key_delete()
            return True
        return False


# =============================================================================
# apply_graph_style
# =============================================================================

def apply_graph_style(plot_widget: pg.PlotWidget,
                      left_label: str = '',
                      left_units: str = '',
                      left_color: str = None,
                      bottom_label: str = 'Time',
                      bottom_units: str = 's',
                      right_label: str = '',
                      right_units: str = '',
                      right_color: str = None) -> None:
    """
    Apply the standard app graph style to a PlotWidget:
      - White background
      - Doubled-size axis tick fonts
      - Coloured axis labels (left = GRAPH_TEMP_COLOR by default,
        right = GRAPH_FLOW_COLOR by default)

    Call once per PlotWidget immediately after make_graph_panel().
    """
    plot_widget.setBackground(GRAPH_BG)

    if left_color is None:
        left_color = GRAPH_TEMP_COLOR
    if right_color is None:
        right_color = GRAPH_FLOW_COLOR

    font_dict = {'family': 'Courier New', 'size': f'{GRAPH_AXIS_FONT_SIZE_PX}px'}

    pi = plot_widget.getPlotItem()
    pi.showGrid(x=True, y=True, alpha=0.2)

    if left_label:
        pi.setLabel('left', left_label, units=left_units,
                    color=left_color, font=font_dict)
    if bottom_label:
        pi.setLabel('bottom', bottom_label, units=bottom_units,
                    color=TEXT_DIM, font=font_dict)
    if right_label:
        pi.showAxis('right')
        pi.setLabel('right', right_label, units=right_units,
                    color=right_color, font=font_dict)

    for axis_name in ('left', 'bottom', 'right', 'top'):
        ax = pi.getAxis(axis_name)
        if ax is not None:
            ax.setStyle(tickFont=_AXIS_FONT)
            ax.setTextPen(pg.mkPen(TEXT))


# =============================================================================
# make_graph_panel
# =============================================================================

def make_graph_panel(title: str, scale: float = 1.0):
    """
    Create a titled graph panel with a toolbar in the top-right corner.

    Toolbar buttons (right to left):
      Export      — save PNG / SVG
      Auto Fit    — reset view to fit all current data
      Add Line    — open dialog, then drag the new line into position
      Clear Lines — remove all annotation lines

    Returns:
        container  — QWidget to add to parent layout
        plot       — pg.PlotWidget (configure axis labels / curves as needed)
        export_btn — QPushButton (already wired; exposed for callers that
                     need to connect additional logic)
    """
    if not isinstance(title, str):
        title = ''

    container = QWidget()
    outer     = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(2)

    # ── Header ────────────────────────────────────────────────────────────────
    header = QWidget()
    header.setObjectName('graph_header')
    hbox   = QHBoxLayout(header)
    hbox.setContentsMargins(8, 4, 4, 4)
    hbox.setSpacing(4)

    lbl = QLabel(title)
    lbl.setObjectName('graph_title')
    lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    container.title_label = lbl

    btn_clear  = QPushButton('✕ Lines')
    btn_clear.setObjectName('btn_export')
    btn_clear.setToolTip('Remove all annotation lines')

    btn_line   = QPushButton('+ Line')
    btn_line.setObjectName('btn_export')
    btn_line.setToolTip('Add a draggable annotation line')

    btn_fit    = QPushButton('⊞ Fit')
    btn_fit.setObjectName('btn_export')
    btn_fit.setToolTip('Auto-fit view to all data')

    btn_export = QPushButton('⬇ Export')
    btn_export.setObjectName('btn_export')
    btn_export.setToolTip('Export graph as PNG or SVG')

    hbox.addWidget(lbl)
    hbox.addWidget(btn_clear,  alignment=Qt.AlignRight)
    hbox.addWidget(btn_line,   alignment=Qt.AlignRight)
    hbox.addWidget(btn_fit,    alignment=Qt.AlignRight)
    hbox.addWidget(btn_export, alignment=Qt.AlignRight)

    # ── Plot ──────────────────────────────────────────────────────────────────
    plot = pg.PlotWidget()
    plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    outer.addWidget(header)
    outer.addWidget(plot)

    # ── Line manager (attach to plot so it stays alive with the widget) ───────
    mgr = _LineManager(plot, parent=container)
    plot._line_manager = mgr   # keep reference; prevents GC

    # ── Wire buttons ──────────────────────────────────────────────────────────
    btn_export.clicked.connect(lambda: export_graph(plot, title))
    btn_fit.clicked.connect(lambda: plot.getPlotItem().getViewBox().autoRange())
    btn_clear.clicked.connect(mgr.clear_lines)
    btn_line.clicked.connect(lambda: _on_add_line_clicked(plot, mgr))

    return container, plot, btn_export


def _on_add_line_clicked(plot: pg.PlotWidget, mgr: _LineManager):
    """Open Add Line dialog and add a movable line to the graph."""
    dlg = _AddLineDialog(plot)
    # Set sensible defaults: Horizontal, Solid, Red
    dlg._axis_cb.setCurrentIndex(0)
    dlg._style_cb.setCurrentIndex(0)
    dlg._color_cb.setCurrentIndex(0)
    if dlg.exec_() != QDialog.Accepted:
        return
    angle, style, color = dlg.values()
    mgr.add_line(angle, style, color)


# =============================================================================
# export_graph
# =============================================================================

def export_graph(plot_widget: pg.PlotWidget, default_stem: str = 'graph'):
    """Open file dialog and export plot_widget as PNG or SVG."""
    if not isinstance(default_stem, str):
        default_stem = 'graph'

    ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
    stem     = default_stem.lower().replace(' ', '_').replace('/', '_')
    filename = f'{stem}_{ts}'

    path, fmt = QFileDialog.getSaveFileName(
        None,
        'Export Graph',
        filename,
        'PNG Image (*.png);;SVG Vector (*.svg)'
    )

    if not path or not isinstance(path, str):
        return

    try:
        if fmt == 'SVG Vector (*.svg)' or path.endswith('.svg'):
            if not path.endswith('.svg'):
                path += '.svg'
            exporter = pgexp.SVGExporter(plot_widget.plotItem)
        else:
            if not path.endswith('.png'):
                path += '.png'
            exporter = pgexp.ImageExporter(plot_widget.plotItem)
        exporter.export(path)
        print(f'Graph exported: {path}')
    except Exception as e:
        print(f'Export error: {e}')
