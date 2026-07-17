"""
UI tests for the PhotoScribe main window.
Requires pytest-qt.
"""
import sys
from pathlib import Path
import pytest
from PySide6.QtCore import Qt

sys.path.insert(0, str(Path(__file__).parent.parent))
from photoscribe import PhotoScribe, PhotoItem


def test_app_instantiation(qapp):
    """Test that the main window can be created without crashing."""
    window = PhotoScribe()
    assert window.windowTitle() == "PhotoScribe"
    window.close()

def test_clear_all_button(qtbot):
    """Test that the 'Clear All' button removes all photos from the list."""
    window = PhotoScribe()
    qtbot.addWidget(window)

    window._on_files_dropped(["/fake/path1.jpg", "/fake/path2.jpg"])
    assert window.photo_table.rowCount() == 2

    qtbot.mouseClick(window.clear_btn, Qt.LeftButton)

    assert window.photo_table.rowCount() == 0
    assert len(window.photos) == 0
    window.close()