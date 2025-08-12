"""
Crop preview widget for showing annotated regions
"""

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .utils import apply_perspective_transform, pil_to_qpixmap, scale_image_to_fit


class CropItem(QFrame):
    """Individual crop item widget"""

    def __init__(self, crop_data: dict, crop_image: QPixmap, parent=None):
        super().__init__(parent)

        self.crop_data = crop_data
        self.crop_image = crop_image

        self.setup_ui()

    def setup_ui(self):
        """Setup the crop item UI"""
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            CropItem {
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: white;
                margin: 5px;
            }
            CropItem:hover {
                border-color: #007acc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Label
        label = QLabel(self.crop_data.get("label", "Crop"))
        label.setFont(QFont("Arial", 12, QFont.Bold))
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #333; border: none;")
        layout.addWidget(label)

        # Image
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumSize(120, 120)
        image_label.setMaximumSize(150, 150)
        image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9;")

        if not self.crop_image.isNull():
            # Scale image to fit label
            scaled_image = scale_image_to_fit(self.crop_image, 140, 140)
            image_label.setPixmap(scaled_image)
        else:
            image_label.setText("No Image")
            image_label.setStyleSheet("border: 1px solid #ccc; color: #999;")

        layout.addWidget(image_label)

        # Dimensions info
        dimensions = (
            f"{self.crop_data.get('width', 0)}×{self.crop_data.get('height', 0)}"
        )
        dim_label = QLabel(dimensions)
        dim_label.setFont(QFont("Arial", 10))
        dim_label.setAlignment(Qt.AlignCenter)
        dim_label.setStyleSheet("color: #666; border: none;")
        layout.addWidget(dim_label)

        # Position info
        position = f"({self.crop_data.get('x', 0)}, {self.crop_data.get('y', 0)})"
        pos_label = QLabel(position)
        pos_label.setFont(QFont("Arial", 9))
        pos_label.setAlignment(Qt.AlignCenter)
        pos_label.setStyleSheet("color: #888; border: none;")
        layout.addWidget(pos_label)

        self.setFixedSize(180, 220)


class CropPreviewWidget(QWidget):
    """Widget for previewing cropped regions"""

    crops_updated = Signal(list)  # List of crop data
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_image = None  # PIL Image
        self.crop_items = []

        self.setup_ui()

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Info label
        self.info_label = QLabel("No annotations to preview")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #666; font-style: italic; padding: 20px;")
        layout.addWidget(self.info_label)

        # Scroll area for crop items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                background-color: #f5f5f5;
            }
        """)

        # Container widget for crops
        self.crops_container = QWidget()
        self.crops_layout = QGridLayout(self.crops_container)
        self.crops_layout.setContentsMargins(10, 10, 10, 10)
        self.crops_layout.setSpacing(10)

        self.scroll_area.setWidget(self.crops_container)
        layout.addWidget(self.scroll_area)

        # Initially hide scroll area
        self.scroll_area.hide()

    def update_crops(self, annotations: list[dict]):
        """Update crop previews from annotations using perspective transformation"""
        try:
            # Clear existing crop items
            self.clear_crops()

            if not annotations or not self.current_image:
                self.show_info_message("No annotations to preview")
                return

            # Create crop items
            crops_data = []
            for i, annotation in enumerate(annotations):
                try:
                    # Handle both polygon and legacy rectangle annotations
                    if annotation.get("type") == "polygon" or "points" in annotation:
                        # New polygon format
                        points = annotation.get("points", [])
                        if len(points) != 4:
                            self.status_message.emit(
                                f"Skipping annotation {i + 1}: needs exactly 4 points"
                            )
                            continue

                        # Apply perspective transformation to get 512x512 rectified image
                        crop_region = apply_perspective_transform(
                            self.current_image, points, output_size=(512, 512)
                        )

                        # Create annotation data for display
                        display_annotation = {
                            "label": annotation.get("label", f"Crop{i + 1}"),
                            "width": 512,
                            "height": 512,
                            "x": min(p[0] for p in points),
                            "y": min(p[1] for p in points),
                        }

                    else:
                        # Legacy rectangle format
                        x = annotation.get("x", 0)
                        y = annotation.get("y", 0)
                        width = annotation.get("width", 0)
                        height = annotation.get("height", 0)

                        if width <= 0 or height <= 0:
                            continue

                        # Simple crop and resize to 512x512
                        crop_region = self.current_image.crop(
                            (x, y, x + width, y + height)
                        )
                        crop_region = crop_region.resize((512, 512), Image.BICUBIC)

                        display_annotation = annotation.copy()
                        display_annotation["width"] = 512
                        display_annotation["height"] = 512

                    # Convert to QPixmap
                    crop_pixmap = pil_to_qpixmap(crop_region)

                    # Create crop item
                    crop_item = CropItem(display_annotation, crop_pixmap, self)

                    # Add to layout (2 columns)
                    row = i // 2
                    col = i % 2
                    self.crops_layout.addWidget(crop_item, row, col)

                    self.crop_items.append(crop_item)

                    # Store crop data for 3D generation
                    crop_info = {
                        "label": display_annotation.get("label", f"Crop{i + 1}"),
                        "width": 512,
                        "height": 512,
                        "image": crop_region,
                        "annotation": annotation,
                        "rectified": True,  # Mark as perspective-corrected
                    }
                    crops_data.append(crop_info)

                except Exception as e:
                    self.status_message.emit(f"Error processing crop {i + 1}: {str(e)}")
                    continue

            if crops_data:
                self.show_crops()
                self.crops_updated.emit(crops_data)
                self.status_message.emit(
                    f"Generated {len(crops_data)} perspective-corrected 512×512 previews"
                )
            else:
                self.show_info_message("No valid crops to display")

        except Exception as e:
            self.status_message.emit(f"Error updating crops: {str(e)}")
            self.show_info_message("Error generating crop previews")

    def clear_crops(self):
        """Clear all crop items"""
        # Remove all crop items from layout
        for crop_item in self.crop_items:
            self.crops_layout.removeWidget(crop_item)
            crop_item.deleteLater()

        self.crop_items.clear()

    def show_crops(self):
        """Show the crops container"""
        self.info_label.hide()
        self.scroll_area.show()

    def show_info_message(self, message: str):
        """Show info message"""
        self.scroll_area.hide()
        self.info_label.setText(message)
        self.info_label.show()

    def set_image(self, image_path: str):
        """Set the source image for cropping"""
        try:
            self.current_image = Image.open(image_path)
            if self.current_image.mode not in ["RGB", "RGBA"]:
                self.current_image = self.current_image.convert("RGB")

        except Exception as e:
            self.status_message.emit(f"Error loading image for crops: {str(e)}")
            self.current_image = None


class CropPreviewWithControls(QWidget):
    """Crop preview widget with additional controls"""

    crops_updated = Signal(list)
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setup_ui()

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)

        # Main crop preview
        self.crop_preview = CropPreviewWidget()
        self.crop_preview.crops_updated.connect(self.crops_updated.emit)
        self.crop_preview.status_message.connect(self.status_message.emit)

        layout.addWidget(self.crop_preview)

        # Control buttons
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(5, 5, 5, 5)

        # Export crops button
        export_btn = QPushButton("Export Crops")
        export_btn.setToolTip("Export individual crop images")
        export_btn.clicked.connect(self.export_crops)
        controls_layout.addWidget(export_btn)

        controls_layout.addStretch()

        # Generate 3D button
        generate_btn = QPushButton("Generate 3D")
        generate_btn.setToolTip("Generate 3D model from crops")
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                font-weight: bold;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #005a9f;
            }
        """)
        generate_btn.clicked.connect(self.generate_3d_model)
        controls_layout.addWidget(generate_btn)

        layout.addLayout(controls_layout)

    def update_crops(self, annotations: list[dict]):
        """Update crop previews"""
        self.crop_preview.update_crops(annotations)

    def set_image(self, image_path: str):
        """Set source image"""
        self.crop_preview.set_image(image_path)

    def export_crops(self):
        """Export individual crop images"""
        # TODO: Implement crop export functionality
        self.status_message.emit("Crop export not yet implemented")

    def generate_3d_model(self):
        """Trigger 3D model generation"""
        # This will be handled by the main window
        self.status_message.emit("3D model generation triggered")


# For compatibility, use the simple version as the main export
CropPreviewWidget = CropPreviewWidget
