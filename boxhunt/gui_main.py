"""
Main entry point for BoxHunt GUI application
"""

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

# Import GUI components
from .gui.main_window import BoxMakerMainWindow


def setup_application() -> QApplication:
    """Setup Qt application"""
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("BoxHunt")
    app.setApplicationDisplayName("BoxHunt - 3D Box Creation Tool")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("BoxHunt")

    # Set application style
    app.setStyle("Fusion")

    return app


def main():
    """Main GUI application entry point"""
    try:
        # Setup application
        app = setup_application()

        # Create main window
        main_window = BoxMakerMainWindow()

        # Show window
        main_window.show()

        # Start event loop
        return app.exec()

    except Exception as e:
        logging.error(f"GUI application error: {e}")

        # Try to show error dialog
        try:
            if "app" in locals():
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Application Error")
                msg.setText(
                    f"An error occurred while starting the application:\n\n{str(e)}"
                )
                msg.exec()
        except Exception:
            pass

        return 1


if __name__ == "__main__":
    sys.exit(main())
