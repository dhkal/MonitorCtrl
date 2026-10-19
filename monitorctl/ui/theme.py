"""界面配色与样式表（浅色主题）。"""

ACCENT = "#2563eb"
ACCENT_SOFT = "#dbeafe"
BG = "#f4f6f9"
CARD = "#ffffff"
BORDER = "#e4e8ef"
TEXT = "#1f2937"
MUTED = "#6b7280"
DANGER = "#dc2626"
OK = "#16a34a"
WARN = "#d97706"

FONT_FAMILY = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif'

QSS = f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}
QWidget#Root {{
    background: {BG};
}}
QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QWidget#Content {{
    background: transparent;
}}
QFrame#WarnCard {{
    background: #fffaf0;
    border: 1px solid #f6e3bd;
    border-radius: 12px;
}}
QFrame#Sidebar {{
    background: {CARD};
    border-right: 1px solid {BORDER};
}}
QLabel#H1 {{
    font-size: 19px;
    font-weight: 700;
    color: #111827;
}}
QLabel#H2 {{
    font-size: 15px;
    font-weight: 600;
    color: #111827;
}}
QLabel#SectionTitle {{
    font-size: 12px;
    font-weight: 700;
    color: {MUTED};
    letter-spacing: 1px;
}}
QLabel#Muted {{
    color: {MUTED};
}}
QLabel#Value {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT};
    font-family: "Consolas", "Cascadia Mono", monospace;
}}
QLabel#Badge {{
    background: {ACCENT_SOFT};
    color: {ACCENT};
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#BadgeGray {{
    background: #f1f3f6;
    color: {MUTED};
    border-radius: 8px;
    padding: 1px 8px;
    font-size: 11px;
}}
QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    background: #f8fafc;
    border-color: #cfd6e0;
}}
QPushButton:pressed {{
    background: #eef2f7;
}}
QPushButton:disabled {{
    color: #aab1bd;
    background: #f7f8fa;
}}
QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background: #1d4ed8;
    border-color: #1d4ed8;
}}
QPushButton#Primary:disabled {{
    background: #9db8f5;
    border-color: #9db8f5;
    color: #eef2ff;
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
    padding: 4px 8px;
}}
QPushButton#Ghost:hover {{
    background: #eef2f7;
    color: {TEXT};
}}
QPushButton#Chip {{
    background: #f6f8fb;
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 5px 14px;
    font-size: 12px;
}}
QPushButton#Chip:hover {{
    border-color: {ACCENT};
    color: {ACCENT};
    background: {ACCENT_SOFT};
}}
QPushButton#Chip:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    color: white;
}}
QPushButton#Step {{
    border-radius: 6px;
    padding: 0px;
    min-width: 24px;
    max-width: 24px;
    min-height: 22px;
    max-height: 22px;
    font-size: 15px;
    font-weight: 700;
    color: {MUTED};
    border: 1px solid transparent;
    background: transparent;
}}
QPushButton#Step:hover {{
    background: #eef2f7;
    color: {TEXT};
    border-color: {BORDER};
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: #e8ecf2;
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: #ffffff;
    border: 2px solid {ACCENT};
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT_SOFT};
}}
QSlider::sub-page:horizontal:disabled {{
    background: #c9d2de;
}}
QSlider::handle:horizontal:disabled {{
    border-color: #c9d2de;
}}
QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 10px;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: #cfd6e0;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
    padding: 4px;
    outline: none;
}}
QLineEdit, QSpinBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 8px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {ACCENT};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #d4dae4;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #bcc5d2;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: #d4dae4;
    border-radius: 5px;
    min-width: 30px;
}}
QListWidget {{
    background: transparent;
    border: none;
}}
QListWidget::item {{
    border-radius: 10px;
    margin: 3px 8px;
    padding: 0px;
}}
QListWidget::item:selected {{
    background: #e9f0ff;
}}
QListWidget::item:hover:!selected {{
    background: #f7f9fc;
}}
QToolTip {{
    background: #111827;
    color: white;
    border: none;
    padding: 5px 8px;
    border-radius: 6px;
}}
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 22px 6px 14px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {ACCENT_SOFT};
    color: {TEXT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 5px 8px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    background: {CARD};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    border: none;
    padding: 7px 16px;
    margin-right: 4px;
    color: {MUTED};
    border-radius: 7px;
}}
QTabBar::tab:selected {{
    background: {ACCENT_SOFT};
    color: {ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
}}
QStatusBar {{
    background: {CARD};
    border-top: 1px solid {BORDER};
    color: {MUTED};
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #c7cedb;
    border-radius: 4px;
    background: white;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}
QSplitter::handle {{
    background: transparent;
    width: 1px;
}}
"""
