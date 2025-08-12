"""
Crop preview widget for showing annotated regions
"""

from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .utils import apply_perspective_transform, pil_to_qpixmap


class CropItem(QFrame):
    """Individual crop item widget with adaptive sizing"""

    def __init__(self, crop_data: dict, crop_image: QPixmap, parent=None):
        super().__init__(parent)

        self.crop_data = crop_data
        self.crop_image = crop_image
        self.image_label = None

        self.setup_ui()

    def setup_ui(self):
        """Setup the crop item UI"""
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("""
            CropItem {
                border: 2px solid #ddd;
                border-radius: 8px;
                background-color: white;
                margin: 0px;
                padding: 0px;
            }
            CropItem:hover {
                border-color: #007acc;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)  # Minimal margins for border clearance
        layout.setSpacing(4)  # Only spacing between label and image

        # Label
        label = QLabel(self.crop_data.get("label", "Crop"))
        label.setFont(QFont("Arial", 10, QFont.Bold))
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #333; border: none;")
        layout.addWidget(label)

        # Image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(
            "border: 1px solid #ccc; background-color: #f9f9f9;"
        )
        self.image_label.setScaledContents(False)  # We'll handle scaling manually

        if not self.crop_image.isNull():
            # Initially set a placeholder - will be updated by set_size
            self.image_label.setPixmap(
                self.crop_image.scaled(
                    100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        else:
            self.image_label.setText("No Image")
            self.image_label.setStyleSheet("border: 1px solid #ccc; color: #999;")

        layout.addWidget(self.image_label, 0, Qt.AlignCenter)

        # Set size policies to allow expansion
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_size(self, width: int, height: int):
        """Set the crop item to a specific size"""
        # Calculate available space for image (minimal margins, only label spacing)
        label_height = 20  # Approximate height for label (reduced font size)
        vertical_margins = 8  # Top + bottom margins (4+4)
        horizontal_margins = 8  # Left + right margins (4+4)
        spacing = 4  # Spacing between label and image
        border_width = 4  # Border width (2px each side)

        available_height = (
            height - label_height - vertical_margins - spacing - border_width
        )
        available_width = width - horizontal_margins - border_width

        max_size = min(available_width, available_height)
        max_size = max(max_size, 60)  # Minimum image size

        if not self.crop_image.isNull():
            # Scale image to fit the available space while maintaining aspect ratio
            scaled_image = self.crop_image.scaled(
                max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )

            # Set the image_label size to match the actual scaled image size
            # This eliminates the white space around the image
            self.image_label.setFixedSize(scaled_image.size())
            self.image_label.setPixmap(scaled_image)
        else:
            # For "No Image" case, use a square area
            self.image_label.setFixedSize(max_size, max_size)

        # Set the widget size
        self.setFixedSize(width, height)


class CropPreviewWidget(QWidget):
    """Widget for previewing cropped regions with adaptive sizing"""

    crops_updated = Signal(list)  # List of crop data
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_image = None  # PIL Image
        self.crop_items = []
        self.crop_data = []  # Store current crop data for export

        self.setup_ui()

    def calculate_optimal_layout(self, num_crops: int) -> tuple[int, int]:
        """Calculate optimal grid layout (rows, cols) with maximum 2 columns"""
        if num_crops <= 0:
            return 1, 1
        elif num_crops == 1:
            return 1, 1
        elif num_crops == 2:
            return 1, 2
        elif num_crops <= 4:
            return 2, 2
        else:
            # For 5 or more crops, use 2 columns with multiple rows
            rows = (num_crops + 1) // 2  # Round up division
            return rows, 2

    def calculate_crop_size(self, num_crops: int) -> tuple[int, int]:
        """Calculate optimal size for each crop item based on available space"""
        if not self.crops_container or num_crops <= 0:
            return 180, 180

        # Get available space from scroll area viewport if container size is not reliable
        if hasattr(self, "scroll_area") and self.scroll_area.viewport():
            viewport_size = self.scroll_area.viewport().size()
            available_width = max(
                viewport_size.width() - 16, 300
            )  # Account for margins
            available_height = max(
                viewport_size.height() - 16, 200
            )  # Account for margins
        else:
            # Fallback to container size
            container_size = self.crops_container.size()
            available_width = max(container_size.width() - 16, 300)
            available_height = max(container_size.height() - 16, 200)

        # Get layout dimensions
        rows, cols = self.calculate_optimal_layout(num_crops)

        # Account for spacing between items (minimal spacing)
        spacing = 4  # Match reduced spacing
        total_spacing_h = spacing * (cols - 1)
        total_spacing_v = spacing * (rows - 1)

        # Calculate item size
        item_width = max((available_width - total_spacing_h) // cols, 120)
        item_height = max((available_height - total_spacing_v) // rows, 120)

        # Keep items roughly square, but allow some variation
        size = min(item_width, item_height)
        size = max(size, 120)  # Minimum size
        size = min(size, 300)  # Maximum size

        return size, size

    def layout_crops_adaptive(self, num_crops: int):
        """Layout crop items using adaptive sizing"""
        if num_crops == 0:
            return

        # Get optimal layout
        rows, cols = self.calculate_optimal_layout(num_crops)

        # Calculate item size based on current container size
        item_width, item_height = self.calculate_crop_size(num_crops)

        # Apply layout and sizes
        for i, crop_item in enumerate(self.crop_items):
            row = i // cols
            col = i % cols

            # Set the size for the crop item
            crop_item.set_size(item_width, item_height)

            # Add to grid layout
            self.crops_layout.addWidget(crop_item, row, col)

    def resizeEvent(self, event):
        """Handle widget resize to update crop sizes"""
        super().resizeEvent(event)

        # Only re-layout if we have crops and the size has changed significantly
        if self.crop_items and event.size() != event.oldSize():
            # Delay the re-layout to avoid too frequent updates
            self.updateGeometry()
            if hasattr(self, "_resize_timer"):
                self._resize_timer.stop()
            else:
                self._resize_timer = QTimer()
                self._resize_timer.setSingleShot(True)
                self._resize_timer.timeout.connect(self._delayed_resize)
            self._resize_timer.start(100)  # 100ms delay

    def _delayed_resize(self):
        """Delayed resize handling to avoid too frequent updates"""
        if self.crop_items:
            # Force geometry update to ensure correct container size
            self.crops_container.updateGeometry()

            num_crops = len(self.crop_items)
            item_width, item_height = self.calculate_crop_size(num_crops)

            # Update each crop item size
            for crop_item in self.crop_items:
                crop_item.set_size(item_width, item_height)

            # Force layout update
            self.crops_layout.update()

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
        self.crops_layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins
        self.crops_layout.setSpacing(4)  # Minimal spacing between crop items

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
                self.crop_data = []  # Clear crop data
                self.show_info_message("No annotations to preview")
                # Emit empty crops to clear 3D viewer textures
                self.crops_updated.emit([])
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

                    # Create crop item without fixed size
                    crop_item = CropItem(display_annotation, crop_pixmap, self)
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
                # Store crop data for export
                self.crop_data = crops_data

                # Use adaptive layout
                self.layout_crops_adaptive(len(crops_data))

                self.show_crops()
                self.crops_updated.emit(crops_data)
                self.status_message.emit(
                    f"Generated {len(crops_data)} perspective-corrected 512×512 previews"
                )
            else:
                self.crop_data = []  # Clear crop data
                self.show_info_message("No valid crops to display")
                # Emit empty crops to clear 3D viewer textures
                self.crops_updated.emit([])

        except Exception as e:
            self.crop_data = []  # Clear crop data on error
            self.status_message.emit(f"Error updating crops: {str(e)}")
            self.show_info_message("Error generating crop previews")
            # Emit empty crops to clear 3D viewer textures on error
            self.crops_updated.emit([])

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


# For compatibility, use the simple version as the main export
CropPreviewWidget = CropPreviewWidget
