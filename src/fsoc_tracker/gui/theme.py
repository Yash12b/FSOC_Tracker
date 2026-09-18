"""Centralized aerospace visual theme.

All colors, fonts, and spacing defined here.
Widgets reference semantic names, never hard-coded values.
"""

from __future__ import annotations


class Colors:
    BACKGROUND = "#070b10"
    PANEL = "#0d141c"
    PANEL_RAISED = "#111b25"
    PANEL_BORDER = "#20303d"
    TEXT = "#e8f0f5"
    MUTED = "#78909c"
    ACCENT = "#22d3ee"
    ACCENT_BLUE = "#4da3ff"
    SUCCESS = "#39e58c"
    WARNING = "#f4b942"
    ERROR = "#ff5c6c"
    TARGET = "#ffb454"
    CENTERLINE = "#29404d"
    GRID = "#12232d"
    CROSSHAIR = "#22d3ee"
    TRAIL = "#1f6feb"
    GROUND_TRUTH = "#a371f7"
    PREDICTED = "#d29922"
    LOCKED = "#3fb950"
    SEARCHING = "#d29922"
    LOST = "#f85149"
    IDLE = "#8b949e"
    TAB_ACTIVE = "#123f55"
    TAB_INACTIVE = "#101a23"
    INPUT_BG = "#080f15"
    INPUT_BORDER = "#29404d"
    SCROLLBAR = "#29404d"
    SCORECARD_PASS = "#3fb950"
    SCORECARD_FAIL = "#f85149"
    SCORECARD_NA = "#8b949e"


class Fonts:
    FAMILY = "Menlo, Consolas, monospace"
    TITLE = f"bold 14px {FAMILY}"
    SUBTITLE = f"bold 12px {FAMILY}"
    BODY = f"11px {FAMILY}"
    SMALL = f"10px {FAMILY}"
    TINY = f"9px {FAMILY}"
    TELEMETRY = f"bold 13px {FAMILY}"
    SCORECARD = f"bold 12px {FAMILY}"
    BUTTON = f"bold 11px {FAMILY}"


class Spacing:
    XS = 2
    SM = 4
    MD = 8
    LG = 12
    XL = 16


class Metrics:
    BORDER = 1
    RADIUS = 2
    HEADER_HEIGHT = 58
    STATUS_HEIGHT = 30
    PANEL_GAP = 6
    CONTENT_MARGIN = 8


def apply_theme(app_or_widget: object) -> str:
    c = Colors
    return f"""
    * {{
        font-family: {Fonts.FAMILY};
        font-size: 11px;
        color: {c.TEXT};
        outline: none;
    }}
    QMainWindow {{
        background-color: {c.BACKGROUND};
    }}
    QFrame#CommandHeader {{
        background-color: {c.PANEL_RAISED};
        border: 1px solid {c.CENTERLINE};
        border-left: 3px solid {c.ACCENT};
    }}
    QLabel#SystemTitle {{
        color: {c.TEXT};
        font-size: 15px;
        font-weight: bold;
        letter-spacing: 1px;
    }}
    QLabel#SystemSubtitle {{
        color: {c.MUTED};
        font-size: 9px;
        letter-spacing: 1px;
    }}
    QLabel#HeaderTelemetry {{
        color: {c.ACCENT};
        font-size: 10px;
        font-weight: bold;
    }}
    QLabel#HeaderState {{
        color: {c.SUCCESS};
        font-size: 11px;
        font-weight: bold;
    }}
    QWidget {{
        background-color: {c.BACKGROUND};
    }}
    QFrame {{
        background-color: {c.PANEL};
        border: 1px solid {c.PANEL_BORDER};
        border-radius: {Metrics.RADIUS}px;
    }}
    QFrame#CameraViewport, QFrame#WorldViewport {{
        border: 1px solid {c.CENTERLINE};
        background-color: #05090d;
    }}
    QLabel {{
        background: transparent;
        border: none;
    }}
    QGroupBox {{
        border: 1px solid {c.PANEL_BORDER};
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 12px;
        font-weight: bold;
        color: {c.MUTED};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    QPushButton {{
        background-color: {c.PANEL_RAISED};
        border: 1px solid {c.PANEL_BORDER};
        border-radius: {Metrics.RADIUS}px;
        padding: 5px 12px;
        font-weight: bold;
        font-size: 11px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        border-color: {c.ACCENT};
        background-color: {c.TAB_ACTIVE};
    }}
    QPushButton:pressed {{
        background-color: {c.ACCENT_BLUE};
        color: {c.BACKGROUND};
    }}
    QPushButton:disabled {{
        color: {c.MUTED};
        border-color: {c.GRID};
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {c.INPUT_BG};
        border: 1px solid {c.INPUT_BORDER};
        border-radius: {Metrics.RADIUS}px;
        padding: 4px 6px;
        color: {c.TEXT};
        min-height: 20px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {c.ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c.PANEL};
        border: 1px solid {c.PANEL_BORDER};
        selection-background-color: {c.TAB_ACTIVE};
    }}
    QTabWidget::pane {{
        border: 1px solid {c.PANEL_BORDER};
        background-color: {c.PANEL};
    }}
    QTabBar::tab {{
        background-color: {c.TAB_INACTIVE};
        color: {c.MUTED};
        padding: 6px 12px;
        border: 1px solid {c.PANEL_BORDER};
        border-bottom: none;
        font-size: 10px;
        font-weight: bold;
    }}
    QTabBar::tab:selected {{
        background-color: {c.TAB_ACTIVE};
        color: {c.TEXT};
    }}
    QTabBar::tab:hover {{
        background-color: {c.GRID};
    }}
    QScrollBar:vertical {{
        background: {c.BACKGROUND};
        width: 8px;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {c.SCROLLBAR};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QCheckBox {{
        spacing: 6px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {c.INPUT_BORDER};
        border-radius: 3px;
        background-color: {c.INPUT_BG};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c.ACCENT};
        border-color: {c.ACCENT};
    }}
    QSplitter::handle {{
        background-color: {c.PANEL_BORDER};
    }}
    QSplitter::handle:horizontal {{
        width: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 2px;
    }}
    QStatusBar {{
        background-color: {c.PANEL};
        border-top: 1px solid {c.PANEL_BORDER};
        color: {c.MUTED};
        font-size: 10px;
        padding: 2px 6px;
    }}
    QMenuBar {{
        background-color: {c.PANEL};
        border-bottom: 1px solid {c.PANEL_BORDER};
    }}
    QMenuBar::item:selected {{
        background-color: {c.TAB_ACTIVE};
    }}
    QMenu {{
        background-color: {c.PANEL};
        border: 1px solid {c.PANEL_BORDER};
    }}
    QMenu::item:selected {{
        background-color: {c.TAB_ACTIVE};
    }}
    QSlider::groove:horizontal {{
        background: {c.PANEL_BORDER};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {c.ACCENT};
        width: 12px;
        height: 12px;
        margin: -4px 0;
        border-radius: 6px;
    }}
    QToolTip {{
        background-color: {c.PANEL_RAISED};
        color: {c.TEXT};
        border: 1px solid {c.ACCENT};
        padding: 4px 6px;
    }}
    QFocusFrame {{
        border: 1px solid {c.ACCENT};
    }}
    QProgressBar {{
        border: 1px solid {c.PANEL_BORDER};
        border-radius: 3px;
        text-align: center;
        background-color: {c.INPUT_BG};
        color: {c.TEXT};
    }}
    QProgressBar::chunk {{
        background-color: {c.ACCENT};
        border-radius: 2px;
    }}
    """
