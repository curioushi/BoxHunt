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
    QSpinBox,
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

        # Box parameters
        self.box_width = 2.0
        self.box_height = 1.5
        self.box_depth = 1.0

        # Rotation
        self.rotation_x = -15.0
        self.rotation_y = 30.0
        self.rotation_z = 0.0

        # Camera
        self.camera_distance = 8.0
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
            light_position = [5.0, 5.0, 5.0, 1.0]

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
        self.rotation_x = -15.0
        self.rotation_y = 30.0
        self.rotation_z = 0.0
        self.camera_distance = 8.0
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

        # Width control
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Width:"))

        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(50, 500)  # 0.5 to 5.0
        self.width_slider.setValue(200)  # 2.0 default
        self.width_slider.valueChanged.connect(self.update_width)
        width_layout.addWidget(self.width_slider)

        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(50, 500)
        self.width_spinbox.setValue(200)
        self.width_spinbox.setSuffix(" cm")
        self.width_spinbox.valueChanged.connect(self.width_slider.setValue)
        self.width_slider.valueChanged.connect(self.width_spinbox.setValue)
        width_layout.addWidget(self.width_spinbox)

        controls_layout.addLayout(width_layout)

        # Height control
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))

        self.height_slider = QSlider(Qt.Horizontal)
        self.height_slider.setRange(50, 500)  # 0.5 to 5.0
        self.height_slider.setValue(150)  # 1.5 default
        self.height_slider.valueChanged.connect(self.update_height)
        height_layout.addWidget(self.height_slider)

        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(50, 500)
        self.height_spinbox.setValue(150)
        self.height_spinbox.setSuffix(" cm")
        self.height_spinbox.valueChanged.connect(self.height_slider.setValue)
        self.height_slider.valueChanged.connect(self.height_spinbox.setValue)
        height_layout.addWidget(self.height_spinbox)

        controls_layout.addLayout(height_layout)

        # Control buttons
        button_layout = QHBoxLayout()

        # Reset view button
        reset_btn = QPushButton("Reset View")
        reset_btn.clicked.connect(self.renderer.reset_view)
        button_layout.addWidget(reset_btn)

        # Auto rotate toggle
        self.rotate_btn = QPushButton("Auto Rotate")
        self.rotate_btn.setCheckable(True)
        self.rotate_btn.toggled.connect(self.renderer.set_auto_rotate)
        button_layout.addWidget(self.rotate_btn)

        controls_layout.addLayout(button_layout)

        layout.addWidget(controls_frame, 0)  # stretch factor 0, no expansion

        # Initial update
        self.update_dimensions()

    def update_width(self, value):
        """Update box width"""
        width = value / 100.0  # Convert to float
        self.renderer.set_box_dimensions(width, self.renderer.box_height)
        self.status_message.emit(f"Width: {width:.1f}")

    def update_height(self, value):
        """Update box height"""
        height = value / 100.0  # Convert to float
        self.renderer.set_box_dimensions(self.renderer.box_width, height)
        self.status_message.emit(f"Height: {height:.1f}")

    def update_dimensions(self):
        """Update all dimensions"""
        width = self.width_slider.value() / 100.0
        height = self.height_slider.value() / 100.0
        self.renderer.set_box_dimensions(width, height)

    def update_box_from_crops(self, crops: list[dict]):
        """Update 3D box based on crop data"""
        self.crop_data = crops

        # Clear existing textures
        for face_name in self.renderer.face_names:
            self.renderer.clear_face_texture(face_name)

        # Analyze crops to estimate box dimensions and apply textures
        if crops:
            # Apply textures to corresponding faces
            texture_count = 0
            for crop in crops:
                label = crop.get("label", "").lower()
                image = crop.get("image")  # PIL Image

                if label and image and label in self.renderer.face_names:
                    self.renderer.set_face_texture(label, image)
                    texture_count += 1

            # Simple estimation based on crop sizes
            total_area = sum(
                crop.get("width", 0) * crop.get("height", 0) for crop in crops
            )
            avg_dimension = math.sqrt(total_area / len(crops)) if crops else 100

            # Scale to reasonable dimensions
            scale_factor = 200 / avg_dimension if avg_dimension > 0 else 1.0

            # Set dimensions based on analysis
            estimated_width = int(avg_dimension * scale_factor * 1.2)
            estimated_height = int(avg_dimension * scale_factor * 0.8)

            # Clamp values
            estimated_width = max(50, min(500, estimated_width))
            estimated_height = max(50, min(500, estimated_height))

            self.width_slider.setValue(estimated_width)
            self.height_slider.setValue(estimated_height)

            self.status_message.emit(
                f"Updated 3D model from {len(crops)} crops ({texture_count} textures applied)"
            )
        else:
            self.status_message.emit("No crop data for 3D model")

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
