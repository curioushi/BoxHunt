"""
Global logger for BoxHunt application
"""

from datetime import datetime
from typing import List, Optional, Protocol


class LogHandler(Protocol):
    """Protocol for log handlers"""
    
    def add_log(self, message: str, level: str) -> None:
        """Add a log message"""
        ...


class GlobalLogger:
    """Global logger singleton"""
    
    _instance: Optional["GlobalLogger"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._handlers: List[LogHandler] = []
        self._initialized = True
    
    def add_handler(self, handler: LogHandler) -> None:
        """Add a log handler"""
        if handler not in self._handlers:
            self._handlers.append(handler)
    
    def remove_handler(self, handler: LogHandler) -> None:
        """Remove a log handler"""
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def _log(self, message: str, level: str) -> None:
        """Internal log method"""
        for handler in self._handlers:
            try:
                handler.add_log(message, level)
            except Exception as e:
                # Avoid recursive logging errors
                print(f"Logger handler error: {e}")
    
    def debug(self, message: str) -> None:
        """Log debug message"""
        self._log(message, "DEBUG")
    
    def info(self, message: str) -> None:
        """Log info message"""
        self._log(message, "INFO")
    
    def warning(self, message: str) -> None:
        """Log warning message"""
        self._log(message, "WARNING")
    
    def warn(self, message: str) -> None:
        """Alias for warning"""
        self.warning(message)
    
    def error(self, message: str) -> None:
        """Log error message"""
        self._log(message, "ERROR")
    
    def success(self, message: str) -> None:
        """Log success message"""
        self._log(message, "SUCCESS")


# Create global logger instance
logger = GlobalLogger()
