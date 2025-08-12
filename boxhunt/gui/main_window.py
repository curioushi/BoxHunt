"""
Main window for BoxHunt 3D box creation tool
"""

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
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)

        # Content splitter
        top_splitter = QSplitter(Qt.Horizontal)

        # Create widgets
        self.image_annotation = ImageAnnotationWidget()
        self.image_annotation.setMinimumSize(400, 300)

        self.crop_preview = CropPreviewWidget()
        self.crop_preview.setMinimumSize(300, 300)

        self.box3d_viewer = Box3DViewerWidget()
        self.box3d_viewer.setMinimumSize(400, 300)

        top_splitter.addWidget(self.image_annotation)
        top_splitter.addWidget(self.crop_preview)
        top_splitter.addWidget(self.box3d_viewer)
        top_splitter.setStretchFactor(0, 1)  # Image annotation takes more space
        top_splitter.setStretchFactor(1, 1)  # Crop preview
        top_splitter.setStretchFactor(2, 1)  # 3D viewer takes more space

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
            logger.info(f"Image loaded: {image_path}")
            self.image_loaded.emit(image_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")
            logger.error(f"Error loading image: {str(e)}")
