
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QToolButton,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt


class CollapsibleGroupBox(QWidget):
    """A collapsible widget that mimics QGroupBox but allows hiding/showing content."""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 12, 0, 0) # QGroupBox's margin-top

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)  # Start collapsed
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: 1px solid #2a2a30;
                border-radius: 8px;
                padding: 4px 8px;
                font-weight: 600;
                font-size: 12px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                color: #a0a0a0;
                text-align: left;
            }
            QToolButton:hover { color: #e8a23a; }
            QToolButton:checked { border-radius: 8px 8px 0 0; }
        """)

        self.content_area = QFrame()
        self.content_area.setVisible(False)
        self.content_area.setStyleSheet("""
            QFrame {
                border: 1px solid #2a2a30;
                border-top: none;
                border-radius: 0 0 8px 8px;
                padding: 12px;
            }
        """)

        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

        self.toggle_button.toggled.connect(self.on_toggled)

    def setLayout(self, layout):
        self.content_area.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)

    def on_toggled(self, checked):
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.content_area.setVisible(checked)
    
    def setChecked(self, checked):
        self.toggle_button.setChecked(checked)
