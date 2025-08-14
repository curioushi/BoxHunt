"""
Main window for BoxHunt 3D box creation tool
"""

import json
import os
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .box3d_viewer import Box3DViewerWidget
from .crop_preview import CropPreviewWidget
from .file_browser import FileBrowserWidget
from .image_annotation import ImageAnnotationWidget
from .log_widget import LogWidget
from .logger import logger


class BoxMakerMainWindow(QMainWindow):
    """Main application window"""

    # Signals
    image_loaded = Signal(str)  # image_path

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_image_path = None
        self.annotations = []  # List of annotation rectangles
        self.output_directory = os.getcwd()  # Default to current working directory

        self.setup_ui()
        self.setup_connections()

        # Auto-maximize on startup
        self.showMaximized()

    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("BoxHunt - 3D Box Creation Tool")
        self.setMinimumSize(1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)

        # Create menu and toolbar
        self.create_menu_bar()
        self.create_toolbar()

        # Create main content area with splitters
        main_splitter = QSplitter(Qt.Vertical)

        # Top section (image processing area)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # Content splitter
        top_splitter = QSplitter(Qt.Horizontal)

        # Create widgets
        self.image_annotation = ImageAnnotationWidget()
        self.image_annotation.setMinimumSize(200, 200)

        self.crop_preview = CropPreviewWidget()
        self.crop_preview.setMinimumSize(200, 100)

        self.box3d_viewer = Box3DViewerWidget()
        self.box3d_viewer.setMinimumSize(200, 100)

        top_splitter.addWidget(self.image_annotation)
        top_splitter.addWidget(self.crop_preview)
        top_splitter.addWidget(self.box3d_viewer)

        # Set strict stretch factors for 2:1:2 ratio
        top_splitter.setStretchFactor(0, 4)  # Image annotation: 4 parts
        top_splitter.setStretchFactor(1, 2)  # Crop preview: 2 parts
        top_splitter.setStretchFactor(2, 2)  # 3D viewer: 2 parts

        # Set initial sizes to enforce ratio
        top_splitter.setSizes([800, 400, 400])

        top_layout.addWidget(top_splitter)

        # Bottom section
        bottom_splitter = QSplitter(Qt.Horizontal)

        # Left: File browser
        self.file_browser = FileBrowserWidget()
        self.file_browser.setMinimumSize(300, 200)

        # Right: Log widget
        self.log_widget = LogWidget()
        self.log_widget.setMinimumSize(400, 200)

        # Register log widget with global logger
        logger.add_handler(self.log_widget)

        bottom_splitter.addWidget(self.file_browser)
        bottom_splitter.addWidget(self.log_widget)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 2)

        # Add widgets to main splitter
        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setStretchFactor(0, 7)  # Top takes 1/2 of space
        main_splitter.setStretchFactor(1, 3)  # Bottom takes 1/2 of space

        main_layout.addWidget(main_splitter)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Test global logger
        logger.info("BoxHunt application initialized")

    def create_menu_bar(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        # Open image
        open_action = QAction("Open Image", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_image)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Open image button
        open_action = QAction("Open", self)
        open_action.setToolTip("Open image file")
        open_action.triggered.connect(self.open_image)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        # Export textures button
        export_action = QAction("Export", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setToolTip("Export all face textures to files")
        export_action.triggered.connect(self.export_textures)
        toolbar.addAction(export_action)

        # Set output directory button
        set_output_dir_action = QAction("Set Output Dir", self)
        set_output_dir_action.setToolTip("Set output directory for exports")
        set_output_dir_action.triggered.connect(self.set_output_directory)
        toolbar.addAction(set_output_dir_action)

    def setup_connections(self):
        """Setup signal-slot connections"""
        # Connect file browser to image loading
        self.file_browser.image_selected.connect(self.load_image_from_path)

        # Connect image annotation to crop preview
        self.image_annotation.annotations_changed.connect(
            self.crop_preview.update_crops
        )

        # Connect crop preview to 3D viewer
        self.crop_preview.crops_updated.connect(self.box3d_viewer.update_box_from_crops)

        # Connect image annotation box ratios to 3D viewer
        self.image_annotation.box_ratios_updated.connect(
            self.box3d_viewer.update_box_dimensions_from_ratios
        )

        # Connect status updates
        self.image_annotation.status_message.connect(self.status_bar.showMessage)
        self.crop_preview.status_message.connect(self.status_bar.showMessage)
        self.box3d_viewer.status_message.connect(self.status_bar.showMessage)

    def open_image(self):
        """Open image file dialog"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff *.webp);;All Files (*)",
        )

        if file_path:
            self.load_image_from_path(file_path)

    def load_image_from_path(self, image_path: str):
        """Load image from file path"""
        try:
            self.current_image_path = image_path

            # Clear all annotations and textures when loading new image
            self.image_annotation.clear_annotations()
            self.box3d_viewer.clear_all_textures()

            # Load the new image
            self.image_annotation.load_image(image_path)
            self.crop_preview.set_image(image_path)  # Set image for crop preview
            self.status_bar.showMessage(f"Loaded: {Path(image_path).name}")
            logger.info(f"Image loaded: {image_path}")
            self.image_loaded.emit(image_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")
            logger.error(f"Error loading image: {str(e)}")

    def set_output_directory(self):
        """Set the output directory for exports"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_directory,
        )

        if directory:
            self.output_directory = directory
            self.status_bar.showMessage(f"Output directory set to: {directory}")
            logger.info(f"Output directory changed to: {directory}")

    def get_texture_fallback_map(self):
        """Get the texture fallback priority mapping"""
        return {
            "front": ["back", "left", "right", "top", "bottom"],
            "back": ["front", "right", "left", "top", "bottom"],
            "left": ["right", "front", "back", "top", "bottom"],
            "right": ["left", "back", "front", "top", "bottom"],
            "top": ["bottom", "front", "back", "left", "right"],
            "bottom": ["top", "front", "back", "left", "right"],
        }

    def export_textures(self):
        """Export all face textures to files with fallback strategy"""
        if not self.current_image_path:
            QMessageBox.warning(
                self, "Warning", "No image loaded. Please load an image first."
            )
            return

        # Get crop data from crop preview
        crops_data = (
            self.crop_preview.crop_data
            if hasattr(self.crop_preview, "crop_data")
            else []
        )

        if not crops_data:
            QMessageBox.warning(
                self,
                "Warning",
                "No crop data available. Please annotate some faces first.",
            )
            return

        try:
            # Create output directory structure
            image_name = Path(self.current_image_path).stem
            export_dir = Path(self.output_directory) / image_name
            export_dir.mkdir(parents=True, exist_ok=True)

            # Build available textures mapping
            available_textures = {}
            for crop in crops_data:
                label = crop.get("label", "").lower()
                if label and "image" in crop:
                    available_textures[label] = crop["image"]

            # Get fallback mapping
            fallback_map = self.get_texture_fallback_map()
            face_names = ["front", "back", "left", "right", "top", "bottom"]

            exported_count = 0

            # Export each face with fallback strategy
            for face_name in face_names:
                texture_image = None
                source_face = face_name

                # Try to get texture for this face
                if face_name in available_textures:
                    texture_image = available_textures[face_name]
                else:
                    # Apply fallback strategy
                    for fallback_face in fallback_map[face_name]:
                        if fallback_face in available_textures:
                            texture_image = available_textures[fallback_face]
                            source_face = fallback_face
                            logger.info(
                                f"Using {fallback_face} texture for {face_name} face"
                            )
                            break

                # Export the texture if available
                if texture_image:
                    output_path = export_dir / f"{face_name}.png"
                    texture_image.save(output_path, "PNG")
                    exported_count += 1

                    if source_face != face_name:
                        logger.info(
                            f"Exported {face_name}.png (using {source_face} texture)"
                        )
                    else:
                        logger.info(f"Exported {face_name}.png")
                else:
                    logger.warning(f"No texture available for {face_name} face")

            # Copy original image to output directory as origin.jpg
            try:
                origin_path = export_dir / "origin.jpg"
                shutil.copy2(self.current_image_path, origin_path)
                logger.info(f"Copied original image to: {origin_path}")
            except Exception as e:
                logger.error(f"Failed to copy original image: {str(e)}")

            # Export annotation data to JSON
            try:
                # Get annotations from image annotation widget
                annotations_data = self.image_annotation.get_annotations()

                # Build annotation info with coordinates and labels
                annotation_info = []
                for annotation in annotations_data:
                    if (
                        annotation.get("type") == "polygon"
                        and len(annotation.get("points", [])) == 4
                    ):
                        annotation_info.append(
                            {
                                "label": annotation.get("label", "Unlabeled"),
                                "points": annotation.get("points", []),
                                "type": "polygon",
                            }
                        )

                # Create complete export data including dimensions and annotations
                export_data = {
                    "dimensions": {
                        "width": self.box3d_viewer.renderer.box_width,
                        "height": self.box3d_viewer.renderer.box_height,
                        "length": self.box3d_viewer.renderer.box_depth,
                    },
                    "annotations": annotation_info,
                }

                # Export complete data to JSON
                data_path = export_dir / "data.json"
                with open(data_path, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)

                logger.info(
                    f"Exported data.json with {len(annotation_info)} annotations"
                )

            except Exception as e:
                logger.error(f"Failed to export annotation data: {str(e)}")

            # Show success message
            if exported_count > 0:
                # Count annotation files
                annotation_count = len(self.image_annotation.get_annotations())
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Exported {exported_count} texture files, data.json ({annotation_count} annotations), and origin.jpg to:\n{export_dir}",
                )
                self.status_bar.showMessage(
                    f"Exported {exported_count} textures, {annotation_count} annotations, and origin image to {export_dir}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Export Failed",
                    "No textures were exported. Please ensure you have annotated at least one face.",
                )

        except Exception as e:
            error_msg = f"Failed to export textures: {str(e)}"
            QMessageBox.critical(self, "Export Error", error_msg)
            logger.error(error_msg)
