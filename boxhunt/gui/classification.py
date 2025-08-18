"""
Image classification functionality for BoxHunt
"""

import base64
from io import BytesIO
from typing import Any

import requests
from PIL import Image
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)

from .logger import logger


class ClassificationUrlDialog(QDialog):
    """Dialog for configuring classification server URL"""

    def __init__(self, default_url="localhost:22335", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Classification Server Configuration")
        self.setModal(True)
        self.setFixedSize(400, 150)

        # Create layout
        layout = QFormLayout()

        # URL input
        self.url_edit = QLineEdit(default_url)
        self.url_edit.setPlaceholderText(
            "Enter classification server URL (e.g., localhost:22335)"
        )
        layout.addRow("Server URL:", self.url_edit)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setLayout(layout)

    def get_url(self) -> str:
        """Get the entered URL"""
        url = self.url_edit.text().strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
        return url


def check_healthy(server_url: str) -> bool:
    """Check if classification server is healthy"""
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.warning(f"Classification server health check failed: {str(e)}")
        return False


def classify_single_image(image_path: str, server_url: str) -> dict[str, Any] | None:
    """Classify a single image using the classification server"""
    try:
        # Load and encode image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Convert to bytes and encode as base64
            img_buffer = BytesIO()
            img.save(img_buffer, format="JPEG")
            img_bytes = img_buffer.getvalue()
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

        # Prepare request data
        request_data = {"image": img_base64, "image_format": "jpeg"}

        # Send request to classification server
        response = requests.post(
            f"{server_url}/inference", json=request_data, timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success" and result.get("data"):
                return result["data"]
            else:
                logger.error(
                    f"Classification failed for {image_path}: {result.get('message', 'Unknown error')}"
                )
                return None
        else:
            logger.error(
                f"Classification server error for {image_path}: HTTP {response.status_code}"
            )
            return None

    except Exception as e:
        logger.error(f"Failed to classify {image_path}: {str(e)}")
        return None
