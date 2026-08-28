"""Dark theme Qt stylesheets for DubStation FreQQ.

Central place for the professional "dub station" look:
    * charcoal background (#1a1a1a);
    * section panels (#252525) with subtle borders (#333);
    * uppercase bold section titles;
    * per-section accent colours (isolator=yellow, reverb=green,
      echo=orange, filter=red, siren=cyan).
"""

# Section accent colours.
COLORS = {
    "bg": "#1a1a1a",
    "panel": "#252525",
    "panel_border": "#333333",
    "text": "#e0e0e0",
    "text_dim": "#9a9a9a",
    "isolator": "#f0c040",
    "reverb": "#40c040",
    "echo": "#ff6600",
    "filter": "#ff4040",
    "siren": "#00ccff",
    "sources": "#c0c0c0",
    "master": "#f0c040",
}


MAIN_STYLE = """
QMainWindow, QWidget#Root {
    background-color: #1a1a1a;
}
QWidget {
    color: #e0e0e0;
    font-family: "Segoe UI", "DejaVu Sans", sans-serif;
    font-size: 11px;
}
QLabel {
    color: #d0d0d0;
}
QLabel#SectionTitle {
    font-weight: bold;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 2px 0;
}
QLabel#Logo {
    font-family: "Consolas", "Courier New", monospace;
    font-size: 20px;
    font-weight: bold;
    color: #f0c040;
    letter-spacing: 2px;
}
QLabel#LogoSub {
    color: #ff6600;
    font-size: 9px;
    letter-spacing: 3px;
}
QFrame#Panel {
    background-color: #252525;
    border: 1px solid #333333;
    border-radius: 6px;
}
QFrame#TopBar {
    background-color: #202020;
    border-bottom: 1px solid #333333;
}
QFrame#BottomStrip {
    border: none;
    border-radius: 0px;
}
QPushButton {
    background-color: #2e2e2e;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 5px 10px;
    color: #e0e0e0;
    font-size: 10px;
}
QPushButton:hover {
    background-color: #3a3a3a;
    border-color: #666666;
}
QPushButton:pressed {
    background-color: #202020;
}
QPushButton#Accent {
    border-color: #f0c040;
    color: #f0c040;
}
QComboBox {
    background-color: #2a2a2a;
    border: 1px solid #444444;
    border-radius: 4px;
    padding: 4px 8px;
    color: #e0e0e0;
    min-height: 20px;
}
QComboBox:hover { border-color: #666666; }
QComboBox QAbstractItemView {
    background-color: #2a2a2a;
    color: #e0e0e0;
    selection-background-color: #3a5a3a;
    border: 1px solid #444;
}
QListWidget {
    background-color: #141414;
    border: 1px solid #333333;
    border-radius: 4px;
    color: #c0c0c0;
    font-family: "Consolas", monospace;
    font-size: 11px;
}
QListWidget::item:selected {
    background-color: #3a4a5a;
    color: #ffffff;
}
QScrollBar:vertical {
    background: #1a1a1a; width: 12px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #444; border-radius: 5px; min-height: 20px;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QToolTip {
    background-color: #2a2a2a;
    color: #e0e0e0;
    border: 1px solid #555;
}
QDialog { background-color: #1a1a1a; }
QCheckBox { color: #d0d0d0; }
QMenu {
    background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #444;
}
QMenu::item:selected { background-color: #3a5a3a; }
"""


def section_title_style(color: str) -> str:
    """Inline style for a coloured section title label."""
    return (f"color: {color}; font-weight: bold; font-size: 10px;"
            f" letter-spacing: 1px;")
