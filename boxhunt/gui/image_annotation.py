"""
2D image annotation widget for marking box faces
"""

import base64
import io
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from PySide6.QtCore import QBuffer, QEvent, QPoint, QRect, QSettings, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressDialog,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .logger import logger
from .utils import pil_to_qpixmap


class AnnotationPolygon:
    """Represents a 4-point polygon annotation"""

    # Static color mapping for annotation labels
    LABEL_COLORS = {
        "front": QColor(255, 0, 0, 100),  # Red
        "back": QColor(0, 255, 0, 100),  # Green
        "left": QColor(0, 0, 255, 100),  # Blue
        "right": QColor(255, 255, 0, 100),  # Yellow
        "top": QColor(255, 0, 255, 100),  # Magenta
        "bottom": QColor(0, 255, 255, 100),  # Cyan
    }

    def __init__(self, points: list[tuple[int, int]] = None, label: str = ""):
        self.points = points or []  # List of (x, y) tuples
        self.label = label
        # Set color based on label
        self.color = self.LABEL_COLORS.get(
            label.lower(), QColor(255, 0, 0, 100)
        )  # Default red
        self.is_complete = len(self.points) == 4

    def add_point(self, x: int, y: int):
        """Add a point to the polygon"""
        if len(self.points) < 4:
            self.points.append((x, y))
            self.is_complete = len(self.points) == 4

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {"points": self.points, "label": self.label, "type": "polygon"}

    @classmethod
    def from_dict(cls, data: dict) -> "AnnotationPolygon":
        """Create from dictionary"""
        return cls(data.get("points", []), data.get("label", ""))

    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is inside polygon using ray casting"""
        if len(self.points) < 4:
            return False

        # Simple point-in-polygon test using ray casting
        inside = False
        p1x, p1y = self.points[0]
        for i in range(4):
            p2x, p2y = self.points[(i + 1) % 4]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def get_bounding_rect(self) -> QRect:
        """Get bounding rectangle of the polygon"""
        if len(self.points) < 4:
            return QRect(0, 0, 0, 0)

        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return QRect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


class VGGTUrlDialog(QDialog):
    """Dialog for configuring VGGT server URL"""

    def __init__(self, default_url="localhost:22334", parent=None):
        super().__init__(parent)
        self.setWindowTitle("VGGT Server Configuration")
        self.setModal(True)
        self.setFixedSize(400, 150)

        # Create layout
        layout = QFormLayout()

        # URL input
        self.url_edit = QLineEdit(default_url)
        self.url_edit.setPlaceholderText(
            "Enter VGGT server URL (e.g., localhost:22334)"
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


class DetectUrlDialog(QDialog):
    """Dialog for configuring Detect server URL"""

    def __init__(self, default_url="localhost:22336", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detect Server Configuration")
        self.setModal(True)
        self.setFixedSize(400, 150)

        # Create layout
        layout = QFormLayout()

        # URL input
        self.url_edit = QLineEdit(default_url)
        self.url_edit.setPlaceholderText(
            "Enter Detect server URL (e.g., localhost:22336)"
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


class ImageCanvas(QLabel):
    """Canvas for displaying image and annotations"""

    annotations_changed = Signal(list)  # List of AnnotationPolygon
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.original_pixmap = QPixmap()
        self.scaled_pixmap = QPixmap()
        self.annotations = []  # List of AnnotationPolygon
        self.current_annotation = None  # Currently being drawn
        self.selected_annotation = None  # Currently selected
        self.drawing_mode = False

        # Annotation labels
        self.annotation_labels = ["front", "back", "left", "right", "top", "bottom"]
        # Use colors from AnnotationPolygon
        self.label_colors = list(AnnotationPolygon.LABEL_COLORS.values())

        # Scale factor from displayed image to original image
        self.scale_factor = 1.0
        self.image_offset = QPoint(0, 0)

        # Magnifier settings
        self.magnifier_size = 120  # Size of the magnifier square
        self.magnifier_zoom = 4.0  # Magnification factor
        self.magnifier_visible = False
        self.magnifier_position = QPoint(20, 20)  # Default top-left position
        self.magnifier_at_bottom_right = False  # Position flag
        self.mouse_pos = QPoint(0, 0)  # Current mouse position

        # Dragging settings
        self.dragging_mode = False
        self.dragged_annotation = None  # The annotation being dragged
        self.dragged_point_index = -1  # Index of the point being dragged
        self.drag_start_pos = QPoint(0, 0)  # Start position of drag

        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.setAlignment(Qt.AlignCenter)
        self.setText("Load an image to start annotating")

        # Enable mouse tracking
        self.setMouseTracking(True)

    def load_image(self, image_path: str):
        """Load image from file path"""
        try:
            # Load with PIL first to ensure compatibility
            pil_image = Image.open(image_path)
            if pil_image.mode not in ["RGB", "RGBA"]:
                pil_image = pil_image.convert("RGB")

            # Convert to QPixmap
            self.original_pixmap = pil_to_qpixmap(pil_image)
            self.scale_image_to_widget()

            # Clear existing annotations
            self.annotations.clear()
            self.current_annotation = None
            self.selected_annotation = None

            self.update()

            # Log image loading (example of using global logger)
            logger.info(
                f"Image loaded in annotation widget: {Path(image_path).name} ({pil_image.width}x{pil_image.height})"
            )

            self.status_message.emit(
                f"Image loaded: {Path(image_path).name} ({pil_image.width}x{pil_image.height})"
            )

        except Exception as e:
            # Log error (example of using global logger)
            logger.error(f"Failed to load image in annotation widget: {str(e)}")

            self.status_message.emit(f"Error loading image: {str(e)}")
            raise

    def scale_image_to_widget(self):
        """Scale image to fit widget while maintaining aspect ratio"""
        if self.original_pixmap.isNull():
            return

        widget_size = self.size()
        image_size = self.original_pixmap.size()

        # Calculate scale factor - allow scaling up to fit widget
        scale_x = widget_size.width() / image_size.width()
        scale_y = widget_size.height() / image_size.height()
        self.scale_factor = min(
            scale_x, scale_y
        )  # Scale to fit while maintaining aspect ratio

        # Scale the pixmap
        new_size = QSize(
            int(image_size.width() * self.scale_factor),
            int(image_size.height() * self.scale_factor),
        )
        self.scaled_pixmap = self.original_pixmap.scaled(
            new_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        # Calculate image position (centered)
        self.image_offset = QPoint(
            (widget_size.width() - new_size.width()) // 2,
            (widget_size.height() - new_size.height()) // 2,
        )

    def widget_to_image_coords(self, widget_point: QPoint) -> QPoint:
        """Convert widget coordinates to original image coordinates"""
        # Adjust for image offset
        image_point = widget_point - self.image_offset

        # Scale to original image coordinates
        if self.scale_factor > 0:
            return QPoint(
                int(image_point.x() / self.scale_factor),
                int(image_point.y() / self.scale_factor),
            )
        return QPoint(0, 0)

    def image_to_widget_coords(self, image_point: QPoint) -> QPoint:
        """Convert original image coordinates to widget coordinates"""
        # Scale from original image coordinates
        scaled_point = QPoint(
            int(image_point.x() * self.scale_factor),
            int(image_point.y() * self.scale_factor),
        )

        # Adjust for image offset
        return scaled_point + self.image_offset

    def find_corner_at_position(
        self, widget_pos: QPoint
    ) -> tuple[AnnotationPolygon, int]:
        """Find if there's a corner point at the given position
        Returns (annotation, point_index) or (None, -1) if no corner found

        Smart selection logic:
        1. If a polygon is selected, prioritize its points
        2. Otherwise, select the closest point within range
        """
        corner_radius = 8  # Pixels within which a corner can be grabbed

        # First, collect all candidate points within range
        candidates = []  # (distance, annotation, point_index)

        for annotation in self.annotations:
            if not annotation.is_complete:
                continue

            for i, point in enumerate(annotation.points):
                # Convert image coordinates to widget coordinates
                image_point = QPoint(point[0], point[1])
                widget_point = self.image_to_widget_coords(image_point)

                # Check distance
                dx = widget_pos.x() - widget_point.x()
                dy = widget_pos.y() - widget_point.y()
                distance = (dx * dx + dy * dy) ** 0.5

                if distance <= corner_radius:
                    candidates.append((distance, annotation, i))

        if not candidates:
            return None, -1

        # If we have a selected annotation, prioritize its points
        if self.selected_annotation:
            selected_candidates = [
                (dist, ann, idx)
                for dist, ann, idx in candidates
                if ann == self.selected_annotation
            ]
            if selected_candidates:
                # Return closest point from selected annotation
                selected_candidates.sort(key=lambda x: x[0])
                return selected_candidates[0][1], selected_candidates[0][2]

        # No selected annotation or no points from selected annotation in range
        # Return closest point overall
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1], candidates[0][2]

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events"""
        if self.original_pixmap.isNull():
            return

        widget_pos = event.position().toPoint()
        image_pos = self.widget_to_image_coords(widget_pos)

        if event.button() == Qt.LeftButton:
            # Check for shift key to enable dragging mode
            shift_pressed = event.modifiers() & Qt.ShiftModifier

            if shift_pressed and not self.drawing_mode:
                # Shift+click: check for corner dragging
                corner_annotation, corner_index = self.find_corner_at_position(
                    widget_pos
                )

                if corner_annotation is not None:
                    # Start dragging a corner
                    self.dragging_mode = True
                    self.dragged_annotation = corner_annotation
                    self.dragged_point_index = corner_index
                    self.drag_start_pos = widget_pos
                    self.selected_annotation = corner_annotation
                    self.status_message.emit(
                        f"Dragging corner {corner_index + 1} of {corner_annotation.label or 'annotation'}"
                    )
                    return
                else:
                    # Shift+click but no corner found: select annotation if clicked inside one
                    clicked_annotation = None
                    for annotation in self.annotations:
                        if annotation.contains_point(image_pos.x(), image_pos.y()):
                            clicked_annotation = annotation
                            break

                    if clicked_annotation:
                        self.selected_annotation = clicked_annotation
                        self.status_message.emit(
                            f"Selected: {clicked_annotation.label}"
                        )
                    return

            # Normal click (no shift): polygon drawing/selection logic
            if not self.drawing_mode:
                # Check if clicking inside existing annotation for selection
                clicked_annotation = None
                for annotation in self.annotations:
                    if annotation.contains_point(image_pos.x(), image_pos.y()):
                        clicked_annotation = annotation
                        break

                if clicked_annotation:
                    # Select annotation
                    self.selected_annotation = clicked_annotation
                    self.status_message.emit(f"Selected: {clicked_annotation.label}")
                else:
                    # Start new polygon
                    self.current_annotation = AnnotationPolygon()
                    self.drawing_mode = True
                    self.selected_annotation = None

                    # Add first point
                    self.current_annotation.add_point(image_pos.x(), image_pos.y())
                    self.status_message.emit(
                        f"Point {len(self.current_annotation.points)}/4 added"
                    )
            else:
                # Continue drawing current polygon
                if self.current_annotation and len(self.current_annotation.points) < 4:
                    self.current_annotation.add_point(image_pos.x(), image_pos.y())
                    self.status_message.emit(
                        f"Point {len(self.current_annotation.points)}/4 added"
                    )

                    if self.current_annotation.is_complete:
                        self.finish_polygon()

        elif event.button() == Qt.RightButton:
            # If in drawing mode, remove last point
            if (
                self.drawing_mode
                and self.current_annotation
                and len(self.current_annotation.points) > 0
            ):
                self.current_annotation.points.pop()
                self.status_message.emit(
                    f"Point removed. {len(self.current_annotation.points)}/4 points"
                )
                if len(self.current_annotation.points) == 0:
                    self.drawing_mode = False
                    self.current_annotation = None
                    self.status_message.emit("Drawing cancelled")
            else:
                # Show context menu for completed annotations
                clicked_annotation = None
                for annotation in self.annotations:
                    if annotation.contains_point(image_pos.x(), image_pos.y()):
                        clicked_annotation = annotation
                        break

                if clicked_annotation:
                    self.show_context_menu(widget_pos, clicked_annotation)

        self.update()

    def show_context_menu(self, pos: QPoint, annotation: AnnotationPolygon):
        """Show context menu for annotation"""
        menu = QMenu(self)

        # Set label submenu
        label_menu = menu.addMenu("Set Label")
        for i, label in enumerate(self.annotation_labels):
            action = label_menu.addAction(label)
            action.triggered.connect(
                lambda checked, lbl=label, idx=i: self.set_annotation_label(
                    annotation, lbl, idx
                )
            )

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.delete_annotation(annotation))

        menu.exec(self.mapToGlobal(pos))

    def set_annotation_label(
        self, annotation: AnnotationPolygon, label: str, color_index: int
    ):
        """Set predefined label for annotation"""
        # Check if this label already exists on another annotation
        for existing_annotation in self.annotations:
            if existing_annotation != annotation and existing_annotation.label == label:
                self.status_message.emit(
                    f"Error: Label '{label}' already exists. Each face can only be annotated once."
                )
                return

        annotation.label = label
        annotation.color = self.label_colors[color_index % len(self.label_colors)]
        self.update()
        self.annotations_changed.emit(self.get_annotations())
        self.status_message.emit(f"Label set to: {label}")

    def delete_annotation(self, annotation: AnnotationPolygon):
        """Delete annotation"""
        if annotation in self.annotations:
            self.annotations.remove(annotation)
            if self.selected_annotation == annotation:
                self.selected_annotation = None
            self.update()
            self.annotations_changed.emit(self.get_annotations())
            self.status_message.emit("Annotation deleted")

    def finish_polygon(self):
        """Finish creating current polygon"""
        if self.current_annotation and self.current_annotation.is_complete:
            # Set default label and color
            default_label = "Unlabeled"
            self.current_annotation.label = default_label
            self.current_annotation.color = QColor(128, 128, 128, 100)  # Gray

            self.annotations.append(self.current_annotation)
            self.selected_annotation = self.current_annotation
            self.current_annotation = None
            self.drawing_mode = False

            self.annotations_changed.emit(self.get_annotations())
            self.status_message.emit("Polygon completed. Right-click to set label.")

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events"""
        if self.original_pixmap.isNull():
            return

        widget_pos = event.position().toPoint()
        image_pos = self.widget_to_image_coords(widget_pos)

        # Always update mouse position and magnifier state
        self.mouse_pos = widget_pos
        self.update_magnifier_position(widget_pos)
        self.magnifier_visible = True

        # Handle corner dragging
        if (
            self.dragging_mode
            and self.dragged_annotation
            and self.dragged_point_index >= 0
        ):
            # Update the dragged point position
            old_point = self.dragged_annotation.points[self.dragged_point_index]
            new_point = (image_pos.x(), image_pos.y())
            self.dragged_annotation.points[self.dragged_point_index] = new_point

            # Emit change signal
            self.annotations_changed.emit(self.get_annotations())
            self.status_message.emit(
                f"Dragging corner {self.dragged_point_index + 1}: "
                f"({old_point[0]}, {old_point[1]}) → ({new_point[0]}, {new_point[1]})"
            )
        else:
            # Update status with mouse position and drawing progress
            if self.drawing_mode and self.current_annotation:
                progress = f"Drawing: {len(self.current_annotation.points)}/4 points"
            else:
                progress = f"Mouse: ({image_pos.x()}, {image_pos.y()})"
            self.status_message.emit(progress)

        # Trigger repaint
        self.update()

    def update_magnifier_position(self, mouse_pos: QPoint):
        """Update magnifier position to avoid collision with mouse cursor"""
        margin = 40  # Minimum distance from cursor to magnifier
        widget_size = self.size()

        # Default position: top-left
        top_left_pos = QPoint(20, 20)
        bottom_right_pos = QPoint(
            widget_size.width() - self.magnifier_size - 20,
            widget_size.height() - self.magnifier_size - 20,
        )

        # Check distance from mouse to current magnifier position
        if not self.magnifier_at_bottom_right:
            # Currently at top-left, check if mouse is too close
            current_center = QPoint(
                top_left_pos.x() + self.magnifier_size // 2,
                top_left_pos.y() + self.magnifier_size // 2,
            )
            distance = (
                (mouse_pos.x() - current_center.x()) ** 2
                + (mouse_pos.y() - current_center.y()) ** 2
            ) ** 0.5

            if distance < self.magnifier_size // 2 + margin:
                # Switch to bottom-right
                self.magnifier_at_bottom_right = True
                self.magnifier_position = bottom_right_pos
            else:
                self.magnifier_position = top_left_pos
        else:
            # Currently at bottom-right, check if mouse is too close
            current_center = QPoint(
                bottom_right_pos.x() + self.magnifier_size // 2,
                bottom_right_pos.y() + self.magnifier_size // 2,
            )
            distance = (
                (mouse_pos.x() - current_center.x()) ** 2
                + (mouse_pos.y() - current_center.y()) ** 2
            ) ** 0.5

            if distance < self.magnifier_size // 2 + margin:
                # Switch to top-left
                self.magnifier_at_bottom_right = False
                self.magnifier_position = top_left_pos
            else:
                self.magnifier_position = bottom_right_pos

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events"""
        if event.button() == Qt.LeftButton and self.dragging_mode:
            # End dragging mode
            self.dragging_mode = False
            annotation_label = self.dragged_annotation.label or "annotation"
            self.status_message.emit(f"Finished dragging corner of {annotation_label}")
            self.dragged_annotation = None
            self.dragged_point_index = -1
        # For polygon mode, we don't need special release handling
        # Points are added on press events

    def leaveEvent(self, event):
        """Handle mouse leave events"""
        self.magnifier_visible = False
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            if self.selected_annotation:
                self.delete_annotation(self.selected_annotation)
        elif event.key() == Qt.Key_Escape:
            # Cancel current drawing or clear selection
            if self.drawing_mode:
                self.current_annotation = None
                self.drawing_mode = False
                self.status_message.emit("Drawing cancelled")
            else:
                self.selected_annotation = None
            self.update()
        # Quick label shortcuts
        elif event.key() == Qt.Key_W:
            # W = top
            if self.selected_annotation:
                self.set_annotation_label(self.selected_annotation, "top", 4)
        elif event.key() == Qt.Key_S:
            # S = front
            if self.selected_annotation:
                self.set_annotation_label(self.selected_annotation, "front", 0)
        elif event.key() == Qt.Key_A:
            # A = left
            if self.selected_annotation:
                self.set_annotation_label(self.selected_annotation, "left", 2)
        elif event.key() == Qt.Key_D:
            # D = right
            if self.selected_annotation:
                self.set_annotation_label(self.selected_annotation, "right", 3)
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent):
        """Custom paint event to draw image and annotations"""
        super().paintEvent(event)

        if self.original_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw scaled image
        painter.drawPixmap(self.image_offset, self.scaled_pixmap)

        # Draw existing annotations
        for annotation in self.annotations:
            self.draw_polygon_annotation(
                painter, annotation, annotation == self.selected_annotation
            )

        # Draw current drawing annotation
        if self.drawing_mode and self.current_annotation:
            self.draw_current_polygon(painter)

        # Draw magnifier
        if self.magnifier_visible:
            self.draw_magnifier(painter)

    def draw_polygon_annotation(
        self, painter: QPainter, annotation: AnnotationPolygon, is_selected: bool
    ):
        """Draw a polygon annotation"""
        if len(annotation.points) < 3:
            return

        # Convert points to widget coordinates
        widget_points = []
        for point in annotation.points:
            widget_point = self.image_to_widget_coords(QPoint(point[0], point[1]))
            widget_points.append(widget_point)

        # Create QPolygon
        qpolygon = QPolygon(widget_points)

        # Draw filled polygon
        painter.setBrush(QBrush(annotation.color))
        if is_selected:
            pen = QPen(QColor(255, 255, 255), 3, Qt.SolidLine)
        else:
            pen = QPen(annotation.color.darker(150), 2, Qt.SolidLine)
        painter.setPen(pen)
        painter.drawPolygon(qpolygon)

        # Draw corner points
        for i, point in enumerate(widget_points):
            # Highlight draggable corners for completed polygons
            if annotation.is_complete:
                # Draw outer ring to indicate draggable corner
                if is_selected or annotation == self.dragged_annotation:
                    painter.setBrush(QBrush(QColor(100, 150, 255, 150)))
                    painter.setPen(QPen(QColor(50, 100, 200), 1))
                    painter.drawEllipse(point, 8, 8)

                # Draw inner corner point
                if (
                    self.dragging_mode
                    and annotation == self.dragged_annotation
                    and i == self.dragged_point_index
                ):
                    # Currently being dragged - red highlight
                    painter.setBrush(QBrush(QColor(255, 100, 100)))
                    painter.setPen(QPen(QColor(200, 0, 0), 2))
                else:
                    # Normal draggable corner
                    painter.setBrush(QBrush(QColor(255, 255, 255)))
                    painter.setPen(QPen(QColor(0, 0, 0), 2))
            else:
                # Non-draggable corner (incomplete polygon)
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.setPen(QPen(QColor(0, 0, 0), 2))

            painter.drawEllipse(point, 4, 4)

        # Draw label
        if annotation.label and len(widget_points) > 0:
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            # Position label at center of polygon
            center_x = sum(p.x() for p in widget_points) // len(widget_points)
            center_y = sum(p.y() for p in widget_points) // len(widget_points)
            label_pos = QPoint(center_x, center_y)
            painter.drawText(label_pos.x() - 20, label_pos.y() - 5, annotation.label)

    def draw_current_polygon(self, painter: QPainter):
        """Draw currently being drawn polygon"""
        if not self.current_annotation or len(self.current_annotation.points) == 0:
            return

        # Convert points to widget coordinates
        widget_points = []
        for point in self.current_annotation.points:
            widget_point = self.image_to_widget_coords(QPoint(point[0], point[1]))
            widget_points.append(widget_point)

        # Draw partial polygon
        painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
        painter.setBrush(QBrush(QColor(255, 0, 0, 50)))

        # Draw lines between existing points
        if len(widget_points) >= 2:
            for i in range(len(widget_points) - 1):
                painter.drawLine(widget_points[i], widget_points[i + 1])

        # Draw points
        for point in widget_points:
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(point, 6, 6)

        # Draw preview line to mouse cursor if in drawing mode
        if len(widget_points) > 0 and len(widget_points) < 4:
            try:
                cursor_pos = self.mapFromGlobal(self.cursor().pos())
                painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.DashLine))
                painter.drawLine(widget_points[-1], cursor_pos)
            except Exception:
                pass  # Ignore cursor position errors

    def draw_magnifier(self, painter: QPainter):
        """Draw magnifier showing zoomed view around mouse cursor"""
        if not self.magnifier_visible or self.original_pixmap.isNull():
            return

        # Calculate source rectangle on original image
        mouse_image_pos = self.widget_to_image_coords(self.mouse_pos)

        # Size of the region to capture from original image
        capture_size = int(
            self.magnifier_size / self.magnifier_zoom / self.scale_factor
        )
        half_capture = capture_size // 2

        # Source rectangle on original image
        src_rect = QRect(
            mouse_image_pos.x() - half_capture,
            mouse_image_pos.y() - half_capture,
            capture_size,
            capture_size,
        )

        # Clamp to image bounds
        image_rect = QRect(
            0, 0, self.original_pixmap.width(), self.original_pixmap.height()
        )
        src_rect = src_rect.intersected(image_rect)

        if src_rect.isEmpty():
            return

        # Extract the region from original pixmap
        cropped_pixmap = self.original_pixmap.copy(src_rect)

        # Scale up the cropped region
        magnified_pixmap = cropped_pixmap.scaled(
            self.magnifier_size,
            self.magnifier_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        # Draw magnifier background
        magnifier_rect = QRect(
            self.magnifier_position.x(),
            self.magnifier_position.y(),
            self.magnifier_size,
            self.magnifier_size,
        )

        # Semi-transparent background
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawRect(magnifier_rect)

        # Draw the magnified image
        center_offset = (self.magnifier_size - magnified_pixmap.width()) // 2
        magnified_rect = QRect(
            self.magnifier_position.x() + center_offset,
            self.magnifier_position.y() + center_offset,
            magnified_pixmap.width(),
            magnified_pixmap.height(),
        )
        painter.drawPixmap(magnified_rect, magnified_pixmap)

        # Draw crosshair at center
        center_x = self.magnifier_position.x() + self.magnifier_size // 2
        center_y = self.magnifier_position.y() + self.magnifier_size // 2
        crosshair_size = 8

        painter.setPen(QPen(QColor(255, 0, 0), 1))
        painter.drawLine(
            center_x - crosshair_size, center_y, center_x + crosshair_size, center_y
        )
        painter.drawLine(
            center_x, center_y - crosshair_size, center_x, center_y + crosshair_size
        )

        # Draw border
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(Qt.transparent))
        painter.drawRect(magnifier_rect)

    def resizeEvent(self, event):
        """Handle widget resize"""
        super().resizeEvent(event)
        if not self.original_pixmap.isNull():
            self.scale_image_to_widget()
            self.update()

    def get_annotations(self) -> list[dict]:
        """Get all annotations as dictionaries"""
        return [annotation.to_dict() for annotation in self.annotations]

    def set_annotations(self, annotations_data: list[dict]):
        """Set annotations from dictionaries"""
        self.annotations = []
        for data in annotations_data:
            if data.get("type") == "polygon" or "points" in data:
                # New polygon format
                self.annotations.append(AnnotationPolygon.from_dict(data))
            else:
                # Legacy rectangle format - convert to polygon
                x, y = data.get("x", 0), data.get("y", 0)
                w, h = data.get("width", 0), data.get("height", 0)
                points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                polygon = AnnotationPolygon(points, data.get("label", ""))
                self.annotations.append(polygon)

        self.selected_annotation = None
        self.current_annotation = None
        self.drawing_mode = False
        self.update()
        self.annotations_changed.emit(self.annotations)

    def load_annotations(self, annotations_data: list[dict]):
        """Load annotations from dictionaries (alias for set_annotations)"""
        self.set_annotations(annotations_data)


class ImageAnnotationWidget(QWidget):
    """Main widget for image annotation"""

    annotations_changed = Signal(list)
    status_message = Signal(str)
    box_ratios_updated = Signal(float, float, float)  # length, width, height ratios

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize QSettings for VGGT URL and Detect URL
        self.settings = QSettings("BoxHunt", "BoxHuntConfig")
        self.vggt_url = self.settings.value("vggt_url", "http://localhost:22334")
        self.detect_url = self.settings.value("detect_url", "http://localhost:22336")

        self.setup_ui()

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet("QToolBar { border: none; }")

        # Clear all button
        clear_btn = QPushButton("Clear All")
        clear_btn.setToolTip("Clear all annotations")
        clear_btn.clicked.connect(self.clear_annotations)
        toolbar.addWidget(clear_btn)

        # Detect button
        detect_btn = QPushButton("Detect")
        detect_btn.setToolTip("Send image to inference server for quad detection (C)")
        detect_btn.clicked.connect(self.detect_inference)
        toolbar.addWidget(detect_btn)

        # VGGT button
        vggt_btn = QPushButton("VGGT")
        vggt_btn.setToolTip("Send image to VGGT server for 3D reconstruction (V)")
        vggt_btn.clicked.connect(self.vggt_inference)
        toolbar.addWidget(vggt_btn)

        toolbar.addSeparator()

        # Instructions label
        instructions = QLabel(
            "Click 4 points to create polygon. Right-click to set label/undo. "
            "Shift+click to drag corners. Quick labels: W=top, S=front, A=left, D=right. C=Detect, V=VGGT"
        )
        instructions.setStyleSheet("color: #666; font-size: 11px;")
        toolbar.addWidget(instructions)

        layout.addWidget(toolbar)

        # Image canvas
        self.canvas = ImageCanvas()
        self.canvas.annotations_changed.connect(self.annotations_changed.emit)
        self.canvas.status_message.connect(self.status_message.emit)

        # Make canvas focusable for key events
        self.canvas.setFocusPolicy(Qt.StrongFocus)

        layout.addWidget(self.canvas)

        # Install event filter for keyboard shortcuts
        self.installEventFilter(self)

    def load_image(self, image_path: str):
        """Load image for annotation"""
        self.canvas.load_image(image_path)
        self.canvas.setFocus()  # Set focus for key events

    def load_annotations(self, annotations_data: list[dict]):
        """Load annotations from dictionaries"""
        self.canvas.load_annotations(annotations_data)

    def get_annotations(self) -> list[dict]:
        """Get all annotations as dictionaries"""
        return self.canvas.get_annotations()

    def clear_annotations(self):
        """Clear all annotations"""
        self.canvas.annotations.clear()
        self.canvas.selected_annotation = None
        self.canvas.update()
        self.annotations_changed.emit([])
        self.status_message.emit("All annotations cleared")

    def vggt_inference(self):
        """Send current image to VGGT server for 3D reconstruction"""
        if not self.canvas.original_pixmap:
            self.status_message.emit("No image loaded")
            return

        # Create progress dialog
        progress = QProgressDialog(
            "Processing with VGGT inference server...", None, 0, 100, self
        )
        progress.setWindowTitle("3D Processing")
        progress.setModal(True)
        progress.setAutoClose(True)
        progress.setMinimumDuration(0)  # Show immediately

        # Remove close button from title bar
        progress.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        # Set dialog size and style
        progress.setMinimumWidth(400)
        progress.setMinimumHeight(100)
        progress.setLabelText("Sending image to 3D inference server...")
        progress.setValue(10)  # Start with some progress

        progress.show()

        try:
            self.status_message.emit("Sending to VGGT server...")

            # Convert QPixmap to PIL Image using QBuffer
            qbuffer = QBuffer()
            qbuffer.open(QBuffer.ReadWrite)
            self.canvas.original_pixmap.save(qbuffer, "PNG")
            qbuffer.seek(0)
            pil_image = Image.open(io.BytesIO(qbuffer.data()))

            # Convert to JPEG bytes
            jpeg_buffer = io.BytesIO()
            pil_image.save(jpeg_buffer, "JPEG")
            jpeg_buffer.seek(0)

            # Encode to base64
            image_b64 = base64.b64encode(jpeg_buffer.getvalue()).decode("utf-8")

            # Prepare request
            request_data = {
                "image": image_b64,
                "image_format": "jpeg",
            }

            # Send request
            logger.info("Sending request to VGGT inference server...")
            progress.setLabelText("Sending request to VGGT server...")
            progress.setValue(30)

            start_time = time.time()

            # Send request with current URL
            try:
                # Extract base URL from saved URL
                base_url = self.vggt_url.replace("/inference", "")
                if base_url.endswith("/"):
                    base_url = base_url[:-1]

                response = requests.post(
                    f"{base_url}/inference", json=request_data, timeout=30
                )
            except requests.exceptions.RequestException:
                # Request failed, show URL configuration dialog
                self._show_url_config_dialog()
                # Try again with new URL
                base_url = self.vggt_url.replace("/inference", "")
                if base_url.endswith("/"):
                    base_url = base_url[:-1]
                response = requests.post(
                    f"{base_url}/inference", json=request_data, timeout=30
                )

            end_time = time.time()
            logger.info(
                f"VGGT inference completed, cost {end_time - start_time} seconds"
            )

            progress.setLabelText("Processing inference results...")
            progress.setValue(70)

            if response.status_code == 200:
                result = response.json()
                if result["status"] == "success":
                    data = result["data"]

                    intrinsic = data["intrinsic"]

                    # Decode world points and confidence
                    world_points = self._decode_base64_numpy(data["world_points"])
                    world_points_conf = self._decode_base64_numpy(
                        data["world_points_conf"]
                    )

                    # # Get colors from processed image
                    # processed_image = self._decode_base64_image(data["processed_image"])
                    # colors_image = np.array(processed_image)

                    # # Save PLY file
                    # # TODO(Haoqi): remove this after testing
                    # progress.setLabelText("Saving PLY file...")
                    # progress.setValue(90)
                    # self._save_ply_file(world_points, world_points_conf, colors_image)
                    # logger.info(f"Intrinsic: {intrinsic}")
                    # logger.info("Postprocessing completed - PLY file saved")

                    # Estimate box dimensions from polygon annotations
                    progress.setLabelText("Estimating box dimensions...")
                    progress.setValue(95)
                    self._estimate_box_dimensions(
                        world_points, world_points_conf, intrinsic
                    )

                    progress.setLabelText("VGGT processing completed!")
                    progress.setValue(100)
                    self.status_message.emit("VGGT processing completed")
                else:
                    self.status_message.emit(f"VGGT error: {result['message']}")
            else:
                # Request failed, show URL configuration dialog
                self._show_url_config_dialog()
                self.status_message.emit(f"VGGT request failed: {response.status_code}")

        except Exception as e:
            self.status_message.emit(f"VGGT error: {str(e)}")
            logger.error(f"VGGT error: {e}")
        finally:
            # Close progress dialog
            progress.close()

    def detect_inference(self):
        """Send current image to Detect server for quad detection"""
        if not self.canvas.original_pixmap:
            self.status_message.emit("No image loaded")
            return

        # Create progress dialog
        progress = QProgressDialog(
            "Processing with Detect inference server...", None, 0, 100, self
        )
        progress.setWindowTitle("Quad Detection")
        progress.setModal(True)
        progress.setAutoClose(True)
        progress.setMinimumDuration(0)  # Show immediately

        # Remove close button from title bar
        progress.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        # Set dialog size and style
        progress.setMinimumWidth(400)
        progress.setMinimumHeight(100)
        progress.setLabelText("Sending image to quad detection server...")
        progress.setValue(10)  # Start with some progress

        progress.show()

        try:
            self.status_message.emit("Sending to Detect server...")

            # Convert QPixmap to PIL Image using QBuffer
            qbuffer = QBuffer()
            qbuffer.open(QBuffer.ReadWrite)
            self.canvas.original_pixmap.save(qbuffer, "PNG")
            qbuffer.seek(0)
            pil_image = Image.open(io.BytesIO(qbuffer.data()))

            # Convert to JPEG bytes
            jpeg_buffer = io.BytesIO()
            pil_image.save(jpeg_buffer, "JPEG")
            jpeg_buffer.seek(0)

            # Encode to base64
            image_b64 = base64.b64encode(jpeg_buffer.getvalue()).decode("utf-8")

            # Prepare request
            request_data = {
                "image": image_b64,
                "image_format": "jpeg",
                "confidence_threshold": 0.6,
            }

            # Send request
            logger.info("Sending request to Detect inference server...")
            progress.setLabelText("Sending request to Detect server...")
            progress.setValue(30)

            start_time = time.time()

            # Send request with current URL
            try:
                # Extract base URL from saved URL
                base_url = self.detect_url.replace("/inference", "")
                if base_url.endswith("/"):
                    base_url = base_url[:-1]

                response = requests.post(
                    f"{base_url}/inference", json=request_data, timeout=30
                )
            except requests.exceptions.RequestException:
                # Request failed, show URL configuration dialog
                self._show_detect_url_config_dialog()
                # Try again with new URL
                base_url = self.detect_url.replace("/inference", "")
                if base_url.endswith("/"):
                    base_url = base_url[:-1]
                response = requests.post(
                    f"{base_url}/inference", json=request_data, timeout=30
                )

            end_time = time.time()
            logger.info(
                f"Detect inference completed, cost {end_time - start_time} seconds"
            )

            progress.setLabelText("Processing detection results...")
            progress.setValue(70)

            if response.status_code == 200:
                result = response.json()
                if result["status"] == "success":
                    data = result["data"]

                    # Clear existing annotations and add new detections
                    progress.setLabelText("Clearing existing annotations...")
                    progress.setValue(85)

                    # Clear all existing annotations
                    self.canvas.annotations.clear()
                    self.canvas.selected_annotation = None
                    self.canvas.current_annotation = None

                    progress.setLabelText("Adding detections to annotations...")
                    progress.setValue(90)

                    self._process_detections(data["detections"])

                    progress.setLabelText("Detection processing completed!")
                    progress.setValue(100)
                    self.status_message.emit(
                        f"Detection completed: {data['total_detections']} quads found"
                    )
                else:
                    self.status_message.emit(f"Detect error: {result['message']}")
            else:
                # Request failed, show URL configuration dialog
                self._show_detect_url_config_dialog()
                self.status_message.emit(
                    f"Detect request failed: {response.status_code}"
                )

        except Exception as e:
            self.status_message.emit(f"Detect error: {str(e)}")
            logger.error(f"Detect error: {e}")
        finally:
            # Close progress dialog
            progress.close()

    def _process_detections(self, detections: list):
        """Process detection results and add to annotations"""
        try:
            # Label mapping from detection server to annotation labels
            label_mapping = {
                0: "front",  # front
                1: "left",  # left
                2: "right",  # right
                3: "top",  # top
            }

            added_count = 0
            for detection in detections:
                label_id = detection["label"]
                confidence = detection["confidence"]
                quad = detection["quad"]

                # Map label ID to annotation label
                annotation_label = label_mapping.get(label_id, "front")

                # Convert quad coordinates to points format
                points = [(int(point[0]), int(point[1])) for point in quad]

                # Create annotation polygon
                annotation = AnnotationPolygon(points, annotation_label)

                # Add to canvas annotations
                self.canvas.annotations.append(annotation)
                added_count += 1

                logger.info(
                    f"Added detection: {annotation_label} (confidence: {confidence:.3f})"
                )

            # Update canvas and emit change signal
            self.canvas.update()
            # Emit annotations_changed signal with dictionary format for crop_preview
            self.annotations_changed.emit(self.canvas.get_annotations())

            logger.info(f"Added {added_count} detections to annotations")

        except Exception as e:
            logger.error(f"Error processing detections: {e}")
            self.status_message.emit(f"Error processing detections: {str(e)}")

    def _decode_base64_image(self, image_b64: str) -> Image.Image:
        """Decode base64 image data"""
        image_bytes = base64.b64decode(image_b64)
        return Image.open(io.BytesIO(image_bytes))

    def _decode_base64_numpy(self, array_b64: str) -> np.ndarray:
        """Decode base64 numpy array"""
        array_bytes = base64.b64decode(array_b64)
        buffer = io.BytesIO(array_bytes)
        return np.load(buffer)

    def _save_ply_file(self, world_points, world_points_conf, colors_image):
        """Save PLY file with filtered points"""
        H, W = world_points.shape[:2]

        # Reshape data
        points_flat = world_points.reshape(-1, 3)
        conf_flat = world_points_conf.reshape(-1)
        colors_flat = colors_image.reshape(-1, 3)

        # Apply confidence filter
        valid_mask = conf_flat >= 2
        filtered_points = points_flat[valid_mask]
        filtered_colors = colors_flat[valid_mask]

        # Save PLY file
        ply_path = "vggt_output_point_cloud.ply"
        with open(ply_path, "w") as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {len(filtered_points)}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
            f.write("end_header\n")

            for i in range(len(filtered_points)):
                x, y, z = filtered_points[i]
                r, g, b = filtered_colors[i]
                f.write(f"{x:.6f} {y:.6f} {z:.6f} {int(r)} {int(g)} {int(b)}\n")

    def set_annotations(self, annotations: list[dict]):
        """Set annotations"""
        self.canvas.set_annotations(annotations)

    def _show_url_config_dialog(self):
        """Show URL configuration dialog when VGGT request fails"""
        try:
            # Extract base URL for display
            display_url = self.vggt_url.replace("http://", "").replace("https://", "")
            if display_url.endswith("/inference"):
                display_url = display_url[:-10]

            dialog = VGGTUrlDialog(display_url, self)
            if dialog.exec() == QDialog.Accepted:
                new_url = dialog.get_url()
                if new_url != self.vggt_url:
                    self.vggt_url = new_url
                    # Save to QSettings
                    self.settings.setValue("vggt_url", new_url)
                    self.settings.sync()
                    logger.info(f"VGGT URL updated to: {new_url}")
                    self.status_message.emit(f"VGGT URL updated to: {new_url}")
        except Exception as e:
            logger.error(f"Error showing URL config dialog: {e}")
            self.status_message.emit(f"Error configuring VGGT URL: {str(e)}")

    def _show_detect_url_config_dialog(self):
        """Show URL configuration dialog when Detect request fails"""
        try:
            # Extract base URL for display
            display_url = self.detect_url.replace("http://", "").replace("https://", "")
            if display_url.endswith("/inference"):
                display_url = display_url[:-10]

            dialog = DetectUrlDialog(display_url, self)
            if dialog.exec() == QDialog.Accepted:
                new_url = dialog.get_url()
                if new_url != self.detect_url:
                    self.detect_url = new_url
                    # Save to QSettings
                    self.settings.setValue("detect_url", new_url)
                    self.settings.sync()
                    logger.info(f"Detect URL updated to: {new_url}")
                    self.status_message.emit(f"Detect URL updated to: {new_url}")
        except Exception as e:
            logger.error(f"Error showing Detect URL config dialog: {e}")
            self.status_message.emit(f"Error configuring Detect URL: {str(e)}")

    def _estimate_box_dimensions(self, world_points, world_points_conf, intrinsic):
        """Estimate box dimensions from polygon annotations using 3D point cloud"""
        try:
            # Get current annotations
            annotations = self.canvas.get_annotations()

            # Check if we have required annotations (top, front, and left/right)
            required_labels = ["top", "front"]
            has_left = any(ann.get("label") == "left" for ann in annotations)
            has_right = any(ann.get("label") == "right" for ann in annotations)

            if not has_left and not has_right:
                logger.warning(
                    "Missing left or right annotation for dimension estimation"
                )
                return

            # Check if all required annotations exist
            missing_labels = []
            for label in required_labels:
                if not any(ann.get("label") == label for ann in annotations):
                    missing_labels.append(label)

            if missing_labels:
                logger.warning(f"Missing annotations: {missing_labels}")
                return

            # Parse camera intrinsic matrix
            intrinsic_matrix = np.array(intrinsic).reshape(3, 3)

            # Get dimensions for each face
            dimensions = {}

            for annotation in annotations:
                label = annotation.get("label")
                if label not in ["top", "front", "left", "right"]:
                    continue

                points = annotation.get("points", [])
                if len(points) != 4:
                    continue

                # Get 3D points within polygon mask
                polygon_points_3d = self._get_points_in_polygon(
                    world_points, world_points_conf, points
                )

                if len(polygon_points_3d) < 10:  # Need enough points for RANSAC
                    logger.warning(f"Insufficient 3D points for {label} face")
                    continue

                # Fit plane using RANSAC
                plane_params = self._fit_plane_ransac(
                    polygon_points_3d, max_iterations=100, threshold=0.02
                )

                if plane_params is None:
                    logger.warning(f"Failed to fit plane for {label} face")
                    continue

                # Calculate face dimensions
                face_dimensions = self._calculate_face_dimensions(
                    points, plane_params, intrinsic_matrix
                )

                if face_dimensions is not None:
                    dimensions[label] = face_dimensions

            # Calculate box dimensions
            if len(dimensions) >= 3:
                self._calculate_box_ratios(dimensions)
            else:
                logger.warning("Insufficient face dimensions for box ratio calculation")

        except Exception as e:
            logger.error(f"Error in box dimension estimation: {e}")

    def _get_points_in_polygon(self, world_points, world_points_conf, polygon_points):
        """Get 3D points that fall within the polygon mask"""
        try:
            H, W = world_points.shape[:2]

            # Create polygon mask
            from PIL import Image, ImageDraw

            # Create a mask image
            mask = Image.new("L", (W, H), 0)
            draw = ImageDraw.Draw(mask)

            # Convert polygon points to PIL format
            pil_points = [(int(p[0]), int(p[1])) for p in polygon_points]
            draw.polygon(pil_points, fill=255)

            # Convert mask to numpy array
            mask_array = np.array(mask)

            # Get points within mask
            valid_mask = (world_points_conf >= 2) & (mask_array > 0)
            valid_points = world_points[valid_mask]

            return valid_points

        except Exception as e:
            logger.error(f"Error getting points in polygon: {e}")
            return np.array([])

    def _fit_plane_ransac(self, points_3d, max_iterations=1000, threshold=0.02):
        """Fit plane to 3D points using RANSAC"""
        try:
            if len(points_3d) < 3:
                return None

            best_plane = None
            best_inliers = 0

            for _ in range(max_iterations):
                # Randomly sample 3 points
                indices = np.random.choice(len(points_3d), 3, replace=False)
                p1, p2, p3 = points_3d[indices]

                # Calculate plane parameters (ax + by + cz + d = 0)
                v1 = p2 - p1
                v2 = p3 - p1
                normal = np.cross(v1, v2)

                if np.linalg.norm(normal) < 1e-6:
                    continue

                normal = normal / np.linalg.norm(normal)
                d = -np.dot(normal, p1)

                # Calculate distances to plane
                distances = np.abs(np.dot(points_3d, normal) + d)

                # Count inliers
                inliers = np.sum(distances < threshold)

                if inliers > best_inliers:
                    best_inliers = inliers
                    best_plane = (normal[0], normal[1], normal[2], d)

            return best_plane

        except Exception as e:
            logger.error(f"Error in RANSAC plane fitting: {e}")
            return None

    def _calculate_face_dimensions(
        self, polygon_points, plane_params, intrinsic_matrix
    ):
        """Calculate face dimensions from polygon corners and plane"""
        try:
            a, b, c, d = plane_params

            # Convert polygon points to homogeneous coordinates
            corners_2d = np.array(polygon_points, dtype=np.float32)

            # Calculate ray directions from camera center
            fx, fy = intrinsic_matrix[0, 0], intrinsic_matrix[1, 1]
            cx, cy = intrinsic_matrix[0, 2], intrinsic_matrix[1, 2]

            # Ray directions in camera coordinates
            ray_dirs = []
            for corner in corners_2d:
                x, y = corner
                # Convert to camera coordinates
                x_cam = (x - cx) / fx
                y_cam = (y - cy) / fy
                ray_dir = np.array([x_cam, y_cam, 1.0])
                ray_dir = ray_dir / np.linalg.norm(ray_dir)
                ray_dirs.append(ray_dir)

            # Calculate intersection points with plane
            intersections = []
            for ray_dir in ray_dirs:
                # Ray-plane intersection: t = -(d + n·o) / (n·d)
                # where o is ray origin (0,0,0), n is plane normal, d is ray direction
                normal = np.array([a, b, c])
                t = -d / np.dot(normal, ray_dir)
                intersection = t * ray_dir
                intersections.append(intersection)

            # Calculate edge lengths
            edges = []
            for i in range(4):
                p1 = intersections[i]
                p2 = intersections[(i + 1) % 4]
                edge_length = np.linalg.norm(p2 - p1)
                edges.append(edge_length)

            # Calculate face dimensions (average of opposite edges)
            L1 = (edges[0] + edges[2]) / 2  # Average of edges 0 and 2
            L2 = (edges[1] + edges[3]) / 2  # Average of edges 1 and 3

            return (L1, L2)

        except Exception as e:
            logger.error(f"Error calculating face dimensions: {e}")
            return None

    def _calculate_box_ratios(self, dimensions):
        """Calculate and display box length:width:height ratios"""
        try:
            # Extract dimensions based on face labels
            length = []
            width = []
            height = []

            if "top" in dimensions:
                L1, L2 = dimensions["top"]
                length.append(L1)  # L1 is length for top face
                width.append(L2)  # L2 is width for top face

            if "front" in dimensions:
                L1, L2 = dimensions["front"]
                height.append(L1)  # L1 is height for front face
                width.append(L2)  # L2 is width for front face

            # Check left/right faces for height and length
            for label in ["left", "right"]:
                if label in dimensions:
                    L1, L2 = dimensions[label]
                    height.append(L1)  # L1 is height for left/right face
                    length.append(L2)  # L2 is length for left/right face

            length = np.mean(length)
            width = np.mean(width)
            height = np.mean(height)

            # Calculate ratios
            if length and width and height:
                # Normalize to length = 1
                width_ratio = width / length
                height_ratio = height / length

                # Format as 1:x:x
                ratio_str = f"1:{width_ratio:.3f}:{height_ratio:.3f}"

                logger.info(
                    f"Box dimensions - Length: {length:.3f}m, Width: {width:.3f}m, Height: {height:.3f}m"
                )
                logger.info(f"Box ratio (L:W:H): {ratio_str}")
                self.status_message.emit(f"Box ratio: {ratio_str}")

                # Emit signal to update 3D viewer with actual dimensions
                self.box_ratios_updated.emit(1.0, width / length, height / length)
            else:
                logger.warning("Could not determine all box dimensions")

        except Exception as e:
            logger.error(f"Error calculating box ratios: {e}")

    def eventFilter(self, source, event):
        """Event filter to handle keyboard shortcuts"""
        if event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_V:
                # V key triggers VGGT inference
                self.vggt_inference()
                return True  # Event handled
            elif key_event.key() == Qt.Key_C:
                # C key triggers Detect inference
                self.detect_inference()
                return True  # Event handled
        return super().eventFilter(source, event)
