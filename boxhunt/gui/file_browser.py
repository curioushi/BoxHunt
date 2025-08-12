"""
File browser widget for selecting images
"""

from pathlib import Path

from PySide6.QtCore import (
    QDir,
    QFileInfo,
    QStandardPaths,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class ImagePreviewWidget(QWidget):
    """Widget for previewing selected images"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_image_path = None
        self.setup_ui()

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Image preview label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(150, 150)
        self.image_label.setMaximumSize(200, 200)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ccc;
                background-color: #f9f9f9;
                color: #666;
            }
        """)
        self.image_label.setText("No Preview")
        layout.addWidget(self.image_label)

        # Image info
        self.info_label = QLabel("No image selected")
        self.info_label.setFont(QFont("Arial", 9))
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: #666; border: none;")
        layout.addWidget(self.info_label)

    def set_image(self, image_path: str):
        """Set image for preview"""
        try:
            self.current_image_path = image_path

            if not Path(image_path).exists():
                self.clear_preview()
                return

            # Load and scale image
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale to fit preview
                scaled_pixmap = pixmap.scaled(
                    180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)

                # Update info
                file_info = QFileInfo(image_path)
                size_mb = file_info.size() / (1024 * 1024)
                info_text = f"{file_info.fileName()}\n{pixmap.width()}×{pixmap.height()}\n{size_mb:.1f} MB"
                self.info_label.setText(info_text)
            else:
                self.clear_preview()

        except Exception as e:
            self.clear_preview()
            self.info_label.setText(f"Error: {str(e)}")

    def clear_preview(self):
        """Clear the preview"""
        self.image_label.clear()
        self.image_label.setText("No Preview")
        self.info_label.setText("No image selected")
        self.current_image_path = None


class FileBrowserWidget(QWidget):
    """File browser widget for image selection"""

    image_selected = Signal(str)  # image_path

    def __init__(self, parent=None):
        super().__init__(parent)

        self.supported_formats = [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"]
        self.current_directory = None

        self.setup_ui()
        self.setup_initial_directory()

    def setup_ui(self):
        """Setup user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Title
        title = QLabel("File Browser")
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)

        # Path navigation
        nav_layout = QHBoxLayout()

        # Quick access buttons
        home_btn = QPushButton("Home")
        home_btn.setToolTip("Go to home directory")
        home_btn.clicked.connect(self.go_to_home)
        nav_layout.addWidget(home_btn)

        pictures_btn = QPushButton("Pictures")
        pictures_btn.setToolTip("Go to pictures directory")
        pictures_btn.clicked.connect(self.go_to_pictures)
        nav_layout.addWidget(pictures_btn)

        # Data directory button (BoxHunt data)
        data_btn = QPushButton("Data")
        data_btn.setToolTip("Go to BoxHunt data directory")
        data_btn.clicked.connect(self.go_to_data_directory)
        nav_layout.addWidget(data_btn)

        nav_layout.addStretch()

        layout.addLayout(nav_layout)

        # Current path display
        self.path_label = QLabel("Current: /")
        self.path_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
        layout.addWidget(self.path_label)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)

        # Directory tree view
        self.setup_tree_view()
        splitter.addWidget(self.tree_view)

        # Right side: image list and preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Image list
        self.image_list = QListWidget()
        self.image_list.setMaximumHeight(150)
        self.image_list.itemClicked.connect(self.on_image_item_clicked)
        self.image_list.itemDoubleClicked.connect(self.on_image_double_clicked)
        right_layout.addWidget(self.image_list)

        # Image preview
        self.image_preview = ImagePreviewWidget()
        right_layout.addWidget(self.image_preview)

        splitter.addWidget(right_widget)

        # Set splitter ratios
        splitter.setStretchFactor(0, 1)  # Tree view
        splitter.setStretchFactor(1, 1)  # Image list and preview

        layout.addWidget(splitter)

        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 9px; padding: 2px;")
        layout.addWidget(self.status_label)

    def setup_tree_view(self):
        """Setup the directory tree view"""
        self.file_system_model = QFileSystemModel()
        self.file_system_model.setRootPath(QDir.currentPath())
        self.file_system_model.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_system_model)
        self.tree_view.setRootIndex(self.file_system_model.index(QDir.homePath()))

        # Hide unnecessary columns
        self.tree_view.hideColumn(1)  # Size
        self.tree_view.hideColumn(2)  # Type
        self.tree_view.hideColumn(3)  # Date

        # Connect selection
        self.tree_view.selectionModel().selectionChanged.connect(
            self.on_directory_selected
        )

    def setup_initial_directory(self):
        """Setup initial directory"""
        # Try to start in user's pictures directory
        pictures_path = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        if Path(pictures_path).exists():
            self.navigate_to_directory(pictures_path)
        else:
            self.navigate_to_directory(QDir.homePath())

    def navigate_to_directory(self, directory_path: str):
        """Navigate to specific directory"""
        try:
            path = Path(directory_path)
            if path.exists() and path.is_dir():
                self.current_directory = str(path)

                # Update tree view
                index = self.file_system_model.index(self.current_directory)
                self.tree_view.setCurrentIndex(index)
                self.tree_view.expand(index)

                # Update path label
                self.path_label.setText(f"Current: {self.current_directory}")

                # Update image list
                self.update_image_list()

        except Exception as e:
            self.status_label.setText(f"Error navigating: {str(e)}")

    def on_directory_selected(self, selected, deselected):
        """Handle directory selection in tree view"""
        try:
            indexes = selected.indexes()
            if indexes:
                index = indexes[0]
                directory_path = self.file_system_model.filePath(index)

                if directory_path != self.current_directory:
                    self.current_directory = directory_path
                    self.path_label.setText(f"Current: {self.current_directory}")
                    self.update_image_list()

        except Exception as e:
            self.status_label.setText(f"Error selecting directory: {str(e)}")

    def update_image_list(self):
        """Update the list of images in current directory"""
        try:
            self.image_list.clear()

            if not self.current_directory:
                return

            directory = Path(self.current_directory)
            if not directory.exists():
                return

            # Find image files
            image_files = []
            for ext in self.supported_formats:
                pattern = f"*{ext}"
                image_files.extend(directory.glob(pattern))
                pattern = f"*{ext.upper()}"
                image_files.extend(directory.glob(pattern))

            # Sort by name
            image_files.sort(key=lambda x: x.name.lower())

            # Add to list
            for image_file in image_files:
                item = QListWidgetItem(image_file.name)
                item.setData(Qt.UserRole, str(image_file))
                item.setToolTip(str(image_file))
                self.image_list.addItem(item)

            # Update status
            count = len(image_files)
            self.status_label.setText(f"Found {count} image{'s' if count != 1 else ''}")

        except Exception as e:
            self.status_label.setText(f"Error updating image list: {str(e)}")

    def on_image_item_clicked(self, item: QListWidgetItem):
        """Handle image item click"""
        try:
            image_path = item.data(Qt.UserRole)
            if image_path:
                # Show preview
                self.image_preview.set_image(image_path)

        except Exception as e:
            self.status_label.setText(f"Error previewing image: {str(e)}")

    def on_image_double_clicked(self, item: QListWidgetItem):
        """Handle image item double click"""
        try:
            image_path = item.data(Qt.UserRole)
            if image_path:
                # Emit signal to load image in main application
                self.image_selected.emit(image_path)
                self.status_label.setText(f"Selected: {Path(image_path).name}")

        except Exception as e:
            self.status_label.setText(f"Error selecting image: {str(e)}")

    def go_to_home(self):
        """Navigate to home directory"""
        home_path = QDir.homePath()
        self.navigate_to_directory(home_path)

    def go_to_pictures(self):
        """Navigate to pictures directory"""
        pictures_path = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        if Path(pictures_path).exists():
            self.navigate_to_directory(pictures_path)
        else:
            self.go_to_home()

    def go_to_data_directory(self):
        """Navigate to BoxHunt data directory"""
        try:
            # Assume data directory is relative to current working directory
            data_path = Path.cwd() / "data"
            if data_path.exists():
                self.navigate_to_directory(str(data_path))
            else:
                # Create data directory if it doesn't exist
                data_path.mkdir(exist_ok=True)
                self.navigate_to_directory(str(data_path))

        except Exception as e:
            self.status_label.setText(f"Error accessing data directory: {str(e)}")

    def get_current_image(self) -> str | None:
        """Get currently selected image path"""
        return self.image_preview.current_image_path

    def refresh(self):
        """Refresh current directory"""
        if self.current_directory:
            self.update_image_list()
