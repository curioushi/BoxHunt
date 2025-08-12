"""
Log widget for displaying application messages
"""

import logging
from datetime import datetime

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogHandler(logging.Handler, QObject):
    """Custom logging handler that emits signals"""

    log_message = Signal(str, str, str)  # timestamp, level, message

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record: logging.LogRecord):
        """Emit log record as signal"""
        try:
            timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            level = record.levelname
            message = self.format(record)
            self.log_message.emit(timestamp, level, message)
        except Exception:
            pass  # Avoid recursive logging errors


class LogWidget(QWidget):
    """Widget for displaying log messages"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.max_lines = 1000  # Maximum number of log lines to keep
        self.auto_scroll = True
        self.log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.visible_levels = set(self.log_levels)

        # Setup logging handler
        self.log_handler = LogHandler()
        self.log_handler.log_message.connect(self.add_log_message)

        self.setup_ui()
        self.setup_logging()

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Controls
        header_layout = QHBoxLayout()
        header_layout.addStretch()

        # Level filter
        level_label = QLabel("Level:")
        level_label.setStyleSheet("font-size: 11px; color: #666;")
        header_layout.addWidget(level_label)

        self.level_combo = QComboBox()
        self.level_combo.addItems(["All"] + self.log_levels)
        self.level_combo.setCurrentText("All")
        self.level_combo.currentTextChanged.connect(self.on_level_filter_changed)
        self.level_combo.setMaximumWidth(100)
        header_layout.addWidget(self.level_combo)

        # Auto scroll checkbox
        self.auto_scroll_cb = QCheckBox("Auto Scroll")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(self.set_auto_scroll)
        header_layout.addWidget(self.auto_scroll_cb)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(clear_btn)

        layout.addLayout(header_layout)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #555;
            }
        """)
        self.log_text.document().setMaximumBlockCount(self.max_lines)
        layout.addWidget(self.log_text)

        # Setup text formats for different log levels
        self.setup_text_formats()

    def setup_text_formats(self):
        """Setup text formatting for different log levels"""
        self.formats = {}

        # DEBUG - Gray
        debug_format = QTextCharFormat()
        debug_format.setForeground(QColor("#808080"))
        self.formats["DEBUG"] = debug_format

        # INFO - White (default)
        info_format = QTextCharFormat()
        info_format.setForeground(QColor("#d4d4d4"))
        self.formats["INFO"] = info_format

        # WARNING - Yellow
        warning_format = QTextCharFormat()
        warning_format.setForeground(QColor("#ffcc00"))
        self.formats["WARNING"] = warning_format

        # ERROR - Red
        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#ff6666"))
        self.formats["ERROR"] = error_format

        # CRITICAL - Bright Red
        critical_format = QTextCharFormat()
        critical_format.setForeground(QColor("#ff0000"))
        critical_format.setFontWeight(QFont.Bold)
        self.formats["CRITICAL"] = critical_format

    def setup_logging(self):
        """Setup logging integration"""
        # Get root logger
        logger = logging.getLogger()

        # Add our handler
        logger.addHandler(self.log_handler)

        # Set formatter
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        self.log_handler.setFormatter(formatter)

        # Initial log message
        self.add_log("Log widget initialized", "INFO")

    def add_log_message(self, timestamp: str, level: str, message: str):
        """Add log message from logging handler"""
        if level in self.visible_levels:
            self.append_formatted_message(timestamp, level, message)

    def add_log(self, message: str, level: str = "INFO"):
        """Add log message directly"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if level in self.visible_levels:
            self.append_formatted_message(timestamp, level, message)

    def append_formatted_message(self, timestamp: str, level: str, message: str):
        """Append formatted message to log text"""
        try:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)

            # Format: [HH:MM:SS] LEVEL: message
            log_line = f"[{timestamp}] {level}: {message}"

            # Apply formatting based on level
            if level in self.formats:
                cursor.setCharFormat(self.formats[level])
            else:
                cursor.setCharFormat(self.formats["INFO"])

            cursor.insertText(log_line + "\n")

            # Auto scroll if enabled
            if self.auto_scroll:
                scrollbar = self.log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())

        except Exception:
            pass  # Avoid recursive logging errors

    def clear_log(self):
        """Clear all log messages"""
        self.log_text.clear()
        self.add_log("Log cleared", "INFO")

    def set_auto_scroll(self, enabled: bool):
        """Enable/disable auto scroll"""
        self.auto_scroll = enabled

    def on_level_filter_changed(self, level_text: str):
        """Handle log level filter change"""
        if level_text == "All":
            self.visible_levels = set(self.log_levels)
        else:
            # Show selected level and higher
            level_index = self.log_levels.index(level_text)
            self.visible_levels = set(self.log_levels[level_index:])

        # Note: This doesn't re-filter existing messages,
        # only affects new messages

    def get_log_text(self) -> str:
        """Get all log text"""
        return self.log_text.toPlainText()

    def save_log_to_file(self, file_path: str):
        """Save log to file"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self.get_log_text())
            self.add_log(f"Log saved to {file_path}", "INFO")
        except Exception as e:
            self.add_log(f"Error saving log: {str(e)}", "ERROR")


class LogWidgetWithTabs(QWidget):
    """Extended log widget with multiple tabs/categories"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setup_ui()

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)

        # For now, just use single log widget
        # Can be extended to support multiple categories
        self.main_log = LogWidget()
        layout.addWidget(self.main_log)

    def add_log(self, message: str, level: str = "INFO", category: str = "main"):
        """Add log message to specified category"""
        # For now, all messages go to main log
        self.main_log.add_log(message, level)

    def clear_log(self, category: str = "main"):
        """Clear log for specified category"""
        self.main_log.clear_log()


# Export the main class for external use
LogWidget = LogWidget
