
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
        self.toggle_button.setObjectName("collapsibleToggle")
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.content_area = QFrame()
        self.content_area.setVisible(False)
        self.content_area.setObjectName("collapsibleContent")
        # The content area needs a layout to hold the actual content
        self.content_layout = QVBoxLayout(self.content_area)

        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

        self.toggle_button.toggled.connect(self.on_toggled)

    def setLayout(self, layout):
        # Add the provided layout into our content area's layout
        self.content_layout.addLayout(layout)

    def on_toggled(self, checked):
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.content_area.setVisible(checked)
    
    def setChecked(self, checked):
        self.toggle_button.setChecked(checked)

    def toggle(self):
        self.toggle_button.toggle()
