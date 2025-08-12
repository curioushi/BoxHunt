"""
2D image annotation widget for marking box faces
"""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
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
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .utils import pil_to_qpixmap


class AnnotationPolygon:
    """Represents a 4-point polygon annotation"""

    def __init__(self, points: list[tuple[int, int]] = None, label: str = ""):
        self.points = points or []  # List of (x, y) tuples
        self.label = label
        self.color = QColor(255, 0, 0, 100)  # Semi-transparent red
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
        self.annotation_labels = ["Front", "Back", "Left", "Right", "Top", "Bottom"]
        self.label_colors = [
            QColor(255, 0, 0, 100),  # Front - Red
            QColor(0, 255, 0, 100),  # Back - Green
            QColor(0, 0, 255, 100),  # Left - Blue
            QColor(255, 255, 0, 100),  # Right - Yellow
            QColor(255, 0, 255, 100),  # Top - Magenta
            QColor(0, 255, 255, 100),  # Bottom - Cyan
        ]

        # Scale factor from displayed image to original image
        self.scale_factor = 1.0
        self.image_offset = QPoint(0, 0)

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
            self.status_message.emit(
                f"Image loaded: {Path(image_path).name} ({pil_image.width}x{pil_image.height})"
            )

        except Exception as e:
            self.status_message.emit(f"Error loading image: {str(e)}")
            raise

    def scale_image_to_widget(self):
        """Scale image to fit widget while maintaining aspect ratio"""
        if self.original_pixmap.isNull():
            return

        widget_size = self.size()
        image_size = self.original_pixmap.size()

        # Calculate scale factor
        scale_x = widget_size.width() / image_size.width()
        scale_y = widget_size.height() / image_size.height()
        self.scale_factor = min(scale_x, scale_y, 1.0)  # Don't scale up

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

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events"""
        if self.original_pixmap.isNull():
            return

        widget_pos = event.position().toPoint()
        image_pos = self.widget_to_image_coords(widget_pos)

        if event.button() == Qt.LeftButton:
            # Check if clicking on existing annotation for selection
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
                # Add point to current polygon or start new one
                if not self.drawing_mode:
                    # Start new polygon
                    self.current_annotation = AnnotationPolygon()
                    self.drawing_mode = True
                    self.selected_annotation = None

                if self.current_annotation and len(self.current_annotation.points) < 4:
                    self.current_annotation.add_point(image_pos.x(), image_pos.y())
                    self.status_message.emit(
                        f"Point {len(self.current_annotation.points)}/4 added"
                    )

                    if self.current_annotation.is_complete:
                        self.finish_polygon()

        elif event.button() == Qt.RightButton:
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

        # Custom label
        custom_action = label_menu.addAction("Custom...")
        custom_action.triggered.connect(lambda: self.set_custom_label(annotation))

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.delete_annotation(annotation))

        menu.exec(self.mapToGlobal(pos))

    def set_annotation_label(
        self, annotation: AnnotationPolygon, label: str, color_index: int
    ):
        """Set predefined label for annotation"""
        annotation.label = label
        annotation.color = self.label_colors[color_index % len(self.label_colors)]
        self.update()
        self.annotations_changed.emit(self.annotations)
        self.status_message.emit(f"Label set to: {label}")

    def set_custom_label(self, annotation: AnnotationPolygon):
        """Set custom label for annotation"""
        text, ok = QInputDialog.getText(self, "Custom Label", "Enter label:")
        if ok and text.strip():
            annotation.label = text.strip()
            self.update()
            self.annotations_changed.emit(self.annotations)
            self.status_message.emit(f"Label set to: {text.strip()}")

    def delete_annotation(self, annotation: AnnotationPolygon):
        """Delete annotation"""
        if annotation in self.annotations:
            self.annotations.remove(annotation)
            if self.selected_annotation == annotation:
                self.selected_annotation = None
            self.update()
            self.annotations_changed.emit(self.annotations)
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

            self.annotations_changed.emit(self.annotations)
            self.status_message.emit("Polygon completed. Right-click to set label.")

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events"""
        if self.original_pixmap.isNull():
            return

        widget_pos = event.position().toPoint()
        image_pos = self.widget_to_image_coords(widget_pos)

        # Update status with mouse position and drawing progress
        if self.drawing_mode and self.current_annotation:
            progress = f"Drawing: {len(self.current_annotation.points)}/4 points"
        else:
            progress = f"Mouse: ({image_pos.x()}, {image_pos.y()})"
        self.status_message.emit(progress)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events"""
        # For polygon mode, we don't need special release handling
        # Points are added on press events
        pass

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
        for point in widget_points:
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawEllipse(point, 4, 4)

        # Draw label
        if annotation.label and len(widget_points) > 0:
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            # Position label at first point
            label_pos = widget_points[0]
            painter.drawText(label_pos.x() + 8, label_pos.y() - 8, annotation.label)

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


class ImageAnnotationWidget(QWidget):
    """Main widget for image annotation"""

    annotations_changed = Signal(list)
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

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

        toolbar.addSeparator()

        # Instructions label
        instructions = QLabel(
            "Click 4 points to create polygon. Right-click to set label. Delete key to remove selected."
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

    def load_image(self, image_path: str):
        """Load image for annotation"""
        self.canvas.load_image(image_path)
        self.canvas.setFocus()  # Set focus for key events

    def clear_annotations(self):
        """Clear all annotations"""
        self.canvas.annotations.clear()
        self.canvas.selected_annotation = None
        self.canvas.update()
        self.annotations_changed.emit([])
        self.status_message.emit("All annotations cleared")

    def get_annotations(self) -> list[dict]:
        """Get current annotations"""
        return self.canvas.get_annotations()

    def set_annotations(self, annotations: list[dict]):
        """Set annotations"""
        self.canvas.set_annotations(annotations)
