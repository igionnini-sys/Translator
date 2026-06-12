"""
main.py
Application entry point.
Run:  python main.py
"""

import sys
import os

# Ensure the project root is on the Python path so relative imports work
# regardless of where the script is launched from.
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.main_window import MainWindow


def main():
    # High-DPI support (Qt 6 handles this automatically but being explicit is safe)
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("AI Translator")
    app.setOrganizationName("AITranslator")

    # Set a clean default font
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
