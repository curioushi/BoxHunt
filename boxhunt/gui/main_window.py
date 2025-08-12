"""
Main window for BoxHunt 3D box creation tool
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
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


class BoxMakerMainWindow(QMainWindow):
    """Main application window"""

    # Signals
    image_loaded = Signal(str)  # image_path

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_image_path = None
        self.annotations = []  # List of annotation rectangles

        self.setup_ui()
        self.setup_connections()

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
        top_layout.setContentsMargins(5, 5, 5, 5)
        top_layout.setSpacing(5)

        # Add titles in one compact row
        titles_layout = QHBoxLayout()

        title1 = QLabel("2D Image Annotation")
        title1.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #333; padding: 2px;"
        )
        title1.setAlignment(Qt.AlignCenter)

        title2 = QLabel("Crop Preview")
        title2.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #333; padding: 2px;"
        )
        title2.setAlignment(Qt.AlignCenter)

        title3 = QLabel("3D Box Viewer")
        title3.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #333; padding: 2px;"
        )
        title3.setAlignment(Qt.AlignCenter)

        titles_layout.addWidget(title1, 2)  # 2:1:2 ratio
        titles_layout.addWidget(title2, 1)
        titles_layout.addWidget(title3, 2)

        top_layout.addLayout(titles_layout)

        # Content splitter
        top_splitter = QSplitter(Qt.Horizontal)

        # Create widgets without titles
        self.image_annotation = ImageAnnotationWidget(show_title=False)
        self.image_annotation.setMinimumSize(400, 300)

        self.crop_preview = CropPreviewWidget(show_title=False)
        self.crop_preview.setMinimumSize(300, 300)

        self.box3d_viewer = Box3DViewerWidget(show_title=False)
        self.box3d_viewer.setMinimumSize(400, 300)

        top_splitter.addWidget(self.image_annotation)
        top_splitter.addWidget(self.crop_preview)
        top_splitter.addWidget(self.box3d_viewer)
        top_splitter.setStretchFactor(0, 2)  # Image annotation takes more space
        top_splitter.setStretchFactor(1, 1)  # Crop preview
        top_splitter.setStretchFactor(2, 2)  # 3D viewer takes more space

        top_layout.addWidget(top_splitter)

        # Bottom section
        bottom_splitter = QSplitter(Qt.Horizontal)

        # Left: File browser
        self.file_browser = FileBrowserWidget()
        self.file_browser.setMinimumSize(300, 200)

        # Right: Log widget
        self.log_widget = LogWidget()
        self.log_widget.setMinimumSize(400, 200)

        bottom_splitter.addWidget(self.file_browser)
        bottom_splitter.addWidget(self.log_widget)
        bottom_splitter.setStretchFactor(0, 1)
        bottom_splitter.setStretchFactor(1, 1)

        # Add widgets to main splitter
        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_splitter)
        main_splitter.setStretchFactor(0, 3)  # Top takes 3/4 of space
        main_splitter.setStretchFactor(1, 1)  # Bottom takes 1/4 of space

        main_layout.addWidget(main_splitter)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

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

        # Save project
        save_action = QAction("Save Project", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)

        # Load project
        load_action = QAction("Load Project", self)
        load_action.setShortcut("Ctrl+L")
        load_action.triggered.connect(self.load_project)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        # Export 3D model
        export_action = QAction("Export 3D Model", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_3d_model)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

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

        # Save project button
        save_action = QAction("Save", self)
        save_action.setToolTip("Save current project")
        save_action.triggered.connect(self.save_project)
        toolbar.addAction(save_action)

        # Load project button
        load_action = QAction("Load", self)
        load_action.setToolTip("Load project file")
        load_action.triggered.connect(self.load_project)
        toolbar.addAction(load_action)

        toolbar.addSeparator()

        # Export 3D model button
        export_action = QAction("Export 3D", self)
        export_action.setToolTip("Export 3D model")
        export_action.triggered.connect(self.export_3d_model)
        toolbar.addAction(export_action)

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
            self.image_annotation.load_image(image_path)
            self.status_bar.showMessage(f"Loaded: {Path(image_path).name}")
            self.log_widget.add_log(f"Image loaded: {image_path}")
            self.image_loaded.emit(image_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")
            self.log_widget.add_log(f"Error loading image: {str(e)}", "ERROR")

    def save_project(self):
        """Save current project to file"""
        if not self.current_image_path:
            QMessageBox.information(self, "Info", "No image loaded to save project for")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            "",
            "BoxHunt Project (*.bhp);;JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            try:
                project_data = {
                    "image_path": self.current_image_path,
                    "annotations": self.image_annotation.get_annotations(),
                    "version": "0.1.0",
                }

                import json

                with open(file_path, "w") as f:
                    json.dump(project_data, f, indent=2)

                self.status_bar.showMessage(f"Project saved: {Path(file_path).name}")
                self.log_widget.add_log(f"Project saved: {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save project: {str(e)}")
                self.log_widget.add_log(f"Error saving project: {str(e)}", "ERROR")

    def load_project(self):
        """Load project from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project",
            "",
            "BoxHunt Project (*.bhp);;JSON Files (*.json);;All Files (*)",
        )

        if file_path:
            try:
                import json

                with open(file_path) as f:
                    project_data = json.load(f)

                # Load image
                image_path = project_data.get("image_path")
                if image_path and Path(image_path).exists():
                    self.load_image_from_path(image_path)

                    # Load annotations
                    annotations = project_data.get("annotations", [])
                    self.image_annotation.set_annotations(annotations)

                    self.status_bar.showMessage(
                        f"Project loaded: {Path(file_path).name}"
                    )
                    self.log_widget.add_log(f"Project loaded: {file_path}")
                else:
                    QMessageBox.warning(self, "Warning", "Image file not found")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load project: {str(e)}")
                self.log_widget.add_log(f"Error loading project: {str(e)}", "ERROR")

    def export_3d_model(self):
        """Export 3D model"""
        if not self.current_image_path:
            QMessageBox.information(self, "Info", "No image loaded to export model for")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export 3D Model",
            "",
            "OBJ Files (*.obj);;glTF Files (*.gltf);;All Files (*)",
        )

        if file_path:
            try:
                # Export model using 3D viewer
                success = self.box3d_viewer.export_model(file_path)
                if success:
                    self.status_bar.showMessage(
                        f"Model exported: {Path(file_path).name}"
                    )
                    self.log_widget.add_log(f"3D model exported: {file_path}")
                else:
                    QMessageBox.warning(self, "Warning", "No 3D model to export")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export model: {str(e)}")
                self.log_widget.add_log(f"Error exporting model: {str(e)}", "ERROR")

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About BoxHunt",
            "BoxHunt 3D Box Creation Tool\n\n"
            "Convert 2D cardboard box images to 3D models\n\n"
            "Version: 0.1.0\n"
            "Built with PySide6 and OpenGL",
        )

    def closeEvent(self, event):
        """Handle window close event"""
        # Ask for confirmation if there are unsaved changes
        reply = QMessageBox.question(
            self,
            "Exit BoxHunt",
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.log_widget.add_log("Application closed")
            event.accept()
        else:
            event.ignore()
