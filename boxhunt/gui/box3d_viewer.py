"""
3D box viewer widget using OpenGL
"""
# ruff: noqa: F403, F405

import math

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

try:
    from OpenGL.GL import *
    from OpenGL.GLU import *

    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False


class Box3DRenderer(QOpenGLWidget):
    """OpenGL widget for rendering 3D box"""

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        if not OPENGL_AVAILABLE:
            self.setStyleSheet("background-color: #f0f0f0;")
            return

        # Box parameters (in meters)
        self.box_width = 1.0  # 1.0m width
        self.box_height = 1.0  # 1.0m height
        self.box_depth = 1.0  # 1.0m length (depth)

        # Rotation - adjusted to view front, top, and right faces simultaneously
        self.rotation_x = 25.0  # Look down from above to see the top
        self.rotation_y = -25.0  # Look from front-right to see front and right faces
        self.rotation_z = 0.0

        # Camera
        self.camera_distance = 4.0
        self.camera_x = 0.0
        self.camera_y = 0.0

        # Mouse interaction
        self.last_pos = None
        self.mouse_pressed = False

        # Face textures - maps face name to PIL Image
        self.face_textures = {}  # Dict: {face_name: PIL_Image}
        self.opengl_textures = {}  # Dict: {face_name: texture_id}
        self.face_names = ["front", "back", "left", "right", "top", "bottom"]

        # Animation
        self.auto_rotate = False
        self.rotate_timer = QTimer()
        self.rotate_timer.timeout.connect(self.auto_rotate_step)

        self.setMinimumSize(300, 300)

    def initializeGL(self):
        """Initialize OpenGL"""
        if not OPENGL_AVAILABLE:
            return

        try:
            # Enable depth testing
            glEnable(GL_DEPTH_TEST)
            glDepthFunc(GL_LEQUAL)

            # Enable face culling
            glEnable(GL_CULL_FACE)
            glCullFace(GL_BACK)

            # Enable texturing
            glEnable(GL_TEXTURE_2D)

            # Set clear color
            glClearColor(0.9, 0.9, 0.9, 1.0)

            # Enable lighting
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)

            # Light properties
            light_ambient = [0.3, 0.3, 0.3, 1.0]
            light_diffuse = [0.8, 0.8, 0.8, 1.0]
            light_position = [3.0, 3.0, 5.0, 1.0]

            glLightfv(GL_LIGHT0, GL_AMBIENT, light_ambient)
            glLightfv(GL_LIGHT0, GL_DIFFUSE, light_diffuse)
            glLightfv(GL_LIGHT0, GL_POSITION, light_position)

            # Material properties
            material_diffuse = [0.7, 0.6, 0.5, 1.0]  # Cardboard color
            material_ambient = [0.3, 0.25, 0.2, 1.0]

            glMaterialfv(GL_FRONT, GL_DIFFUSE, material_diffuse)
            glMaterialfv(GL_FRONT, GL_AMBIENT, material_ambient)

        except Exception as e:
            self.status_message.emit(f"OpenGL initialization error: {str(e)}")

    def create_texture_from_image(self, image: Image.Image) -> int:
        """Create OpenGL texture from PIL image"""
        if not OPENGL_AVAILABLE:
            return 0

        try:
            # Convert to RGBA format
            if image.mode != "RGBA":
                image = image.convert("RGBA")

            # Resize to power-of-2 dimensions for compatibility
            width, height = image.size
            new_width = 1
            new_height = 1
            while new_width < width:
                new_width *= 2
            while new_height < height:
                new_height *= 2

            # Clamp to maximum size
            max_size = 512
            new_width = min(new_width, max_size)
            new_height = min(new_height, max_size)

            if (new_width, new_height) != image.size:
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert to numpy array
            img_data = np.array(image, dtype=np.uint8)

            # Generate texture
            texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture_id)

            # Set texture parameters
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

            # Upload texture data
            glTexImage2D(
                GL_TEXTURE_2D,
                0,
                GL_RGBA,
                new_width,
                new_height,
                0,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
                img_data,
            )

            glBindTexture(GL_TEXTURE_2D, 0)
            return texture_id

        except Exception as e:
            self.status_message.emit(f"Texture creation error: {str(e)}")
            return 0

    def set_face_texture(self, face_name: str, image: Image.Image):
        """Set texture for a specific face"""
        if not OPENGL_AVAILABLE or not image:
            return

        face_name = face_name.lower()
        if face_name not in self.face_names:
            return

        # Store the image
        self.face_textures[face_name] = image

        # Create OpenGL texture
        texture_id = self.create_texture_from_image(image)
        if texture_id > 0:
            # Delete old texture if exists
            if face_name in self.opengl_textures:
                old_texture = self.opengl_textures[face_name]
                if old_texture > 0:
                    glDeleteTextures([old_texture])

            self.opengl_textures[face_name] = texture_id

        self.update()

    def clear_face_texture(self, face_name: str):
        """Clear texture for a specific face"""
        face_name = face_name.lower()
        if face_name in self.face_textures:
            del self.face_textures[face_name]

        if face_name in self.opengl_textures:
            texture_id = self.opengl_textures[face_name]
            if texture_id > 0:
                glDeleteTextures([texture_id])
            del self.opengl_textures[face_name]

        self.update()

    def resizeGL(self, width, height):
        """Resize OpenGL viewport"""
        if not OPENGL_AVAILABLE:
            return

        try:
            glViewport(0, 0, width, height)

            # Set projection matrix
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()

            aspect_ratio = width / height if height > 0 else 1.0
            gluPerspective(45.0, aspect_ratio, 0.1, 100.0)

            glMatrixMode(GL_MODELVIEW)

        except Exception as e:
            self.status_message.emit(f"OpenGL resize error: {str(e)}")

    def paintGL(self):
        """Render OpenGL scene"""
        if not OPENGL_AVAILABLE:
            # Draw fallback message
            from PySide6.QtGui import QPainter

            painter = QPainter(self)
            painter.drawText(self.rect(), Qt.AlignCenter, "OpenGL not available")
            return

        try:
            # Clear buffers
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # Reset modelview matrix
            glLoadIdentity()

            # Position camera
            glTranslatef(self.camera_x, self.camera_y, -self.camera_distance)

            # Apply rotations
            glRotatef(self.rotation_x, 1.0, 0.0, 0.0)
            glRotatef(self.rotation_y, 0.0, 1.0, 0.0)
            glRotatef(self.rotation_z, 0.0, 0.0, 1.0)

            # Draw the box
            self.draw_box()

        except Exception as e:
            self.status_message.emit(f"OpenGL render error: {str(e)}")

    def draw_box(self):
        """Draw a 3D cardboard box with textures"""
        if not OPENGL_AVAILABLE:
            return

        try:
            w, h, d = self.box_width, self.box_height, self.box_depth

            # Define face data: [vertices, normal, texture_coords, face_name]
            face_data = [
                # Front face
                {
                    "vertices": [
                        (-w / 2, -h / 2, d / 2),
                        (w / 2, -h / 2, d / 2),
                        (w / 2, h / 2, d / 2),
                        (-w / 2, h / 2, d / 2),
                    ],
                    "normal": (0, 0, 1),
                    "texcoords": [
                        (0, 1),
                        (1, 1),
                        (1, 0),
                        (0, 0),
                    ],  # Flipped Y coordinates
                    "face_name": "front",
                    "color": [0.8, 0.7, 0.6, 1.0],
                },
                # Back face
                {
                    "vertices": [
                        (w / 2, -h / 2, -d / 2),
                        (-w / 2, -h / 2, -d / 2),
                        (-w / 2, h / 2, -d / 2),
                        (w / 2, h / 2, -d / 2),
                    ],
                    "normal": (0, 0, -1),
                    "texcoords": [
                        (0, 1),
                        (1, 1),
                        (1, 0),
                        (0, 0),
                    ],  # Flipped Y coordinates
                    "face_name": "back",
                    "color": [0.6, 0.5, 0.4, 1.0],
                },
                # Left face
                {
                    "vertices": [
                        (-w / 2, -h / 2, -d / 2),
                        (-w / 2, -h / 2, d / 2),
                        (-w / 2, h / 2, d / 2),
                        (-w / 2, h / 2, -d / 2),
                    ],
                    "normal": (-1, 0, 0),
                    "texcoords": [
                        (0, 1),
                        (1, 1),
                        (1, 0),
                        (0, 0),
                    ],  # Flipped Y coordinates
                    "face_name": "left",
                    "color": [0.7, 0.6, 0.5, 1.0],
                },
                # Right face
                {
                    "vertices": [
                        (w / 2, -h / 2, d / 2),
                        (w / 2, -h / 2, -d / 2),
                        (w / 2, h / 2, -d / 2),
                        (w / 2, h / 2, d / 2),
                    ],
                    "normal": (1, 0, 0),
                    "texcoords": [
                        (0, 1),
                        (1, 1),
                        (1, 0),
                        (0, 0),
                    ],  # Flipped Y coordinates
                    "face_name": "right",
                    "color": [0.7, 0.6, 0.5, 1.0],
                },
                # Top face
                {
                    "vertices": [
                        (-w / 2, h / 2, d / 2),
                        (w / 2, h / 2, d / 2),
                        (w / 2, h / 2, -d / 2),
                        (-w / 2, h / 2, -d / 2),
                    ],
                    "normal": (0, 1, 0),
                    "texcoords": [
                        (0, 1),
                        (1, 1),
                        (1, 0),
                        (0, 0),
                    ],  # Flipped Y coordinates
                    "face_name": "top",
                    "color": [0.75, 0.65, 0.55, 1.0],
                },
                # Bottom face
                {
                    "vertices": [
                        (-w / 2, -h / 2, -d / 2),
                        (w / 2, -h / 2, -d / 2),
                        (w / 2, -h / 2, d / 2),
                        (-w / 2, -h / 2, d / 2),
                    ],
                    "normal": (0, -1, 0),
                    "texcoords": [
                        (0, 1),
                        (1, 1),
                        (1, 0),
                        (0, 0),
                    ],  # Flipped Y coordinates
                    "face_name": "bottom",
                    "color": [0.65, 0.55, 0.45, 1.0],
                },
            ]

            # Draw each face
            for face in face_data:
                face_name = face["face_name"]
                has_texture = face_name in self.opengl_textures

                if has_texture:
                    # Bind texture
                    glBindTexture(GL_TEXTURE_2D, self.opengl_textures[face_name])
                    glEnable(GL_TEXTURE_2D)
                    # Set white color for textured surfaces
                    glMaterialfv(GL_FRONT, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
                else:
                    # No texture, use default color
                    glDisable(GL_TEXTURE_2D)
                    glMaterialfv(GL_FRONT, GL_DIFFUSE, face["color"])

                # Draw face
                glBegin(GL_QUADS)
                glNormal3fv(face["normal"])
                for i in range(4):
                    if has_texture:
                        glTexCoord2fv(face["texcoords"][i])
                    glVertex3fv(face["vertices"][i])
                glEnd()

                if has_texture:
                    glBindTexture(GL_TEXTURE_2D, 0)

            # Draw wireframe for edges
            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glColor3f(0.2, 0.2, 0.2)
            glLineWidth(1.5)

            glBegin(GL_LINES)
            for face in face_data:
                vertices = face["vertices"]
                for i in range(4):
                    v1 = vertices[i]
                    v2 = vertices[(i + 1) % 4]
                    glVertex3fv(v1)
                    glVertex3fv(v2)
            glEnd()

            glEnable(GL_LIGHTING)

        except Exception as e:
            self.status_message.emit(f"Box drawing error: {str(e)}")

    def mousePressEvent(self, event):
        """Handle mouse press for rotation"""
        if event.button() == Qt.LeftButton:
            self.last_pos = event.position().toPoint()
            self.mouse_pressed = True

    def mouseMoveEvent(self, event):
        """Handle mouse move for rotation"""
        if self.mouse_pressed and self.last_pos:
            current_pos = event.position().toPoint()
            dx = current_pos.x() - self.last_pos.x()
            dy = current_pos.y() - self.last_pos.y()

            # Update rotation
            self.rotation_y += dx * 0.5
            self.rotation_x += dy * 0.5

            # Clamp rotation
            self.rotation_x = max(-90, min(90, self.rotation_x))

            self.last_pos = current_pos
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = False
            self.last_pos = None

    def wheelEvent(self, event):
        """Handle mouse wheel for zoom"""
        delta = event.angleDelta().y()
        zoom_factor = 0.001 * delta
        self.camera_distance -= zoom_factor
        self.camera_distance = max(2.0, min(20.0, self.camera_distance))
        self.update()

    def clear_all_textures(self):
        """Clear all face textures"""
        for face_name in list(self.face_names):
            self.clear_face_texture(face_name)
        self.update()

    def set_box_dimensions(self, width: float, height: float, depth: float = None):
        """Set box dimensions"""
        self.box_width = width
        self.box_height = height
        if depth is not None:
            self.box_depth = depth
        self.update()

    def set_auto_rotate(self, enabled: bool):
        """Enable/disable auto rotation"""
        self.auto_rotate = enabled
        if enabled:
            self.rotate_timer.start(50)  # 50ms = ~20 FPS
        else:
            self.rotate_timer.stop()

    def auto_rotate_step(self):
        """Single step of auto rotation"""
        if self.auto_rotate:
            self.rotation_y += 1.0
            if self.rotation_y >= 360.0:
                self.rotation_y -= 360.0
            self.update()

    def reset_view(self):
        """Reset view to default"""
        self.rotation_x = 25.0  # Look down from above to see the top
        self.rotation_y = -25.0  # Look from front-right to see front and right faces
        self.rotation_z = 0.0
        self.camera_distance = 4.0
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.update()


class Box3DViewerWidget(QWidget):
    """3D box viewer with controls"""

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.crop_data = []
        self.setup_ui()

    def linear_to_log_slider(
        self, value: float, min_val: float = 0.1, max_val: float = 10.0
    ) -> int:
        """Convert linear value to logarithmic slider position (0-1000)"""
        if value <= min_val:
            return 0
        if value >= max_val:
            return 1000
        log_min = math.log10(min_val)
        log_max = math.log10(max_val)
        log_val = math.log10(value)
        return int(1000 * (log_val - log_min) / (log_max - log_min))

    def log_slider_to_linear(
        self, slider_pos: int, min_val: float = 0.1, max_val: float = 10.0
    ) -> float:
        """Convert logarithmic slider position (0-1000) to linear value"""
        if slider_pos <= 0:
            return min_val
        if slider_pos >= 1000:
            return max_val
        log_min = math.log10(min_val)
        log_max = math.log10(max_val)
        log_val = log_min + (slider_pos / 1000.0) * (log_max - log_min)
        return 10**log_val

    def get_texture_fallback_map(self):
        """Get the texture fallback priority mapping (only first priority for 3D viewer)"""
        return {
            "front": "back",
            "back": "front",
            "left": "right",
            "right": "left",
            "top": "bottom",
            "bottom": "top",
        }

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # 3D renderer
        self.renderer = Box3DRenderer()
        self.renderer.status_message.connect(self.status_message.emit)
        # Renderer should expand to take all available space
        self.renderer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.renderer, 1)  # stretch factor 1

        # Controls frame
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.StyledPanel)
        controls_frame.setStyleSheet(
            "QFrame { background-color: #f8f8f8; border: 1px solid #ddd; }"
        )
        # Set fixed height for controls frame
        controls_frame.setFixedHeight(120)
        controls_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(8)

        # Width control (logarithmic scale)
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))

        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(0, 1000)  # 0.1 to 10.0 m (logarithmic)
        self.width_slider.setValue(self.linear_to_log_slider(1.0))  # 1.0m default
        self.width_slider.valueChanged.connect(self.update_width)
        width_layout.addWidget(self.width_slider)

        self.width_label = QLabel("1.00")
        self.width_label.setMinimumWidth(60)
        width_layout.addWidget(self.width_label)

        controls_layout.addLayout(width_layout)

        # Height control (logarithmic scale)
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))

        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(0, 1000)  # 0.1 to 10.0 m (logarithmic)
        self.height_slider.setValue(self.linear_to_log_slider(1.0))  # 1.0m default
        self.height_slider.valueChanged.connect(self.update_height)
        height_layout.addWidget(self.height_slider)

        self.height_label = QLabel("1.00")
        self.height_label.setMinimumWidth(60)
        height_layout.addWidget(self.height_label)

        controls_layout.addLayout(height_layout)

        # Control buttons
        button_layout = QHBoxLayout()

        # Reset size button
        reset_size_btn = QPushButton("Reset Size")
        reset_size_btn.clicked.connect(self.reset_size)
        button_layout.addWidget(reset_size_btn)

        # Reset view button
        reset_view_btn = QPushButton("Reset View")
        reset_view_btn.clicked.connect(self.renderer.reset_view)
        button_layout.addWidget(reset_view_btn)

        # Auto rotate toggle
        self.rotate_btn = QPushButton("Auto Rotate")
        self.rotate_btn.setCheckable(True)
        self.rotate_btn.toggled.connect(self.renderer.set_auto_rotate)
        button_layout.addWidget(self.rotate_btn)

        controls_layout.addLayout(button_layout)

        layout.addWidget(controls_frame, 0)  # stretch factor 0, no expansion

        # Initial update
        self.update_dimensions()

    def update_width(self, slider_value):
        """Update box width from logarithmic slider"""
        width = self.log_slider_to_linear(slider_value)
        self.renderer.set_box_dimensions(
            width, self.renderer.box_height, self.renderer.box_depth
        )
        self.width_label.setText(f"{width:.2f}")
        self.status_message.emit(f"Width: {width:.2f}")

    def update_height(self, slider_value):
        """Update box height from logarithmic slider"""
        height = self.log_slider_to_linear(slider_value)
        self.renderer.set_box_dimensions(
            self.renderer.box_width, height, self.renderer.box_depth
        )
        self.height_label.setText(f"{height:.2f}")
        self.status_message.emit(f"Height: {height:.2f}")

    def update_dimensions(self):
        """Update all dimensions"""
        width = self.log_slider_to_linear(self.width_slider.value())
        height = self.log_slider_to_linear(self.height_slider.value())
        # Keep depth fixed at 1.0
        self.renderer.set_box_dimensions(width, height, 1.0)

    def reset_size(self):
        """Reset box size to 1x1x1 meters"""
        # Reset sliders to 1.0
        target_value = self.linear_to_log_slider(1.0)

        self.width_slider.setValue(target_value)
        self.height_slider.setValue(target_value)

        # Update labels
        self.width_label.setText("1.00")
        self.height_label.setText("1.00")

        # Update 3D model
        self.renderer.set_box_dimensions(1.0, 1.0, 1.0)

        # Show status message
        self.status_message.emit("Box size reset to 1.00 x 1.00 x 1.00")

    def update_box_from_crops(self, crops: list[dict]):
        """Update 3D box based on crop data"""
        self.crop_data = crops

        # Clear existing textures
        for face_name in self.renderer.face_names:
            self.renderer.clear_face_texture(face_name)

        # Analyze crops to estimate box dimensions and apply textures
        if crops:
            # Build available textures mapping
            available_textures = {}
            for crop in crops:
                label = crop.get("label", "").lower()
                image = crop.get("image")  # PIL Image
                if label and image and label in self.renderer.face_names:
                    available_textures[label] = image

            # Get fallback mapping
            fallback_map = self.get_texture_fallback_map()

            # Apply textures to all faces with fallback strategy
            texture_count = 0
            for face_name in self.renderer.face_names:
                texture_image = None
                source_face = face_name

                # Try to get texture for this face
                if face_name in available_textures:
                    texture_image = available_textures[face_name]
                else:
                    # Apply symmetry fallback (only first priority)
                    fallback_face = fallback_map.get(face_name)
                    if fallback_face and fallback_face in available_textures:
                        texture_image = available_textures[fallback_face]
                        source_face = fallback_face

                # Apply texture if available
                if texture_image:
                    self.renderer.set_face_texture(face_name, texture_image)
                    texture_count += 1

                    if source_face != face_name:
                        # Log when using symmetry fallback
                        pass  # We don't log in 3D viewer to avoid spam

            # Don't auto-adjust dimensions - user controls them manually
            # Only apply textures, keep current box dimensions unchanged

            applied_msg = f"Applied {texture_count} textures to 3D model"
            if texture_count > len(available_textures):
                applied_msg += f" (with {texture_count - len(available_textures)} symmetry fallbacks)"

            self.status_message.emit(applied_msg)
        else:
            self.status_message.emit("No crop data for 3D model")

    def clear_all_textures(self):
        """Clear all textures from the renderer"""
        self.renderer.clear_all_textures()

    def export_model(self, file_path: str) -> bool:
        """Export 3D model to file"""
        try:
            # Simple OBJ export
            if file_path.lower().endswith(".obj"):
                return self.export_obj(file_path)
            else:
                self.status_message.emit("Only OBJ format supported")
                return False

        except Exception as e:
            self.status_message.emit(f"Export error: {str(e)}")
            return False

    def export_obj(self, file_path: str) -> bool:
        """Export as OBJ file"""
        try:
            w, h, d = (
                self.renderer.box_width,
                self.renderer.box_height,
                self.renderer.box_depth,
            )

            # Define vertices
            vertices = [
                f"v {-w / 2} {-h / 2} {d / 2}",  # 1
                f"v {w / 2} {-h / 2} {d / 2}",  # 2
                f"v {w / 2} {h / 2} {d / 2}",  # 3
                f"v {-w / 2} {h / 2} {d / 2}",  # 4
                f"v {-w / 2} {-h / 2} {-d / 2}",  # 5
                f"v {w / 2} {-h / 2} {-d / 2}",  # 6
                f"v {w / 2} {h / 2} {-d / 2}",  # 7
                f"v {-w / 2} {h / 2} {-d / 2}",  # 8
            ]

            # Define faces (OBJ uses 1-based indexing)
            faces = [
                "f 1 2 3 4",  # Front
                "f 5 8 7 6",  # Back
                "f 1 4 8 5",  # Left
                "f 2 6 7 3",  # Right
                "f 4 3 7 8",  # Top
                "f 1 5 6 2",  # Bottom
            ]

            with open(file_path, "w") as f:
                f.write("# BoxHunt 3D Box Export\n")
                f.write(f"# Dimensions: {w:.2f} x {h:.2f} x {d:.2f}\n\n")

                for vertex in vertices:
                    f.write(vertex + "\n")

                f.write("\n")

                for face in faces:
                    f.write(face + "\n")

            return True

        except Exception as e:
            self.status_message.emit(f"OBJ export error: {str(e)}")
            return False
