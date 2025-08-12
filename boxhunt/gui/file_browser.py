"""
File browser widget for selecting images
"""

from pathlib import Path

from PySide6.QtCore import (
    QDir,
    QEvent,
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
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
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
        # Set fixed size policy to prevent resizing
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(150, 150)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #ccc;
                background-color: #f9f9f9;
                color: #666;
            }
        """)
        self.image_label.setText("No Preview")
        layout.addWidget(self.image_label)

        # Set size policy for the entire preview widget
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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
                # Scale to fixed size to maintain layout stability
                target_size = self.image_label.size()
                if target_size.width() < 100 or target_size.height() < 100:
                    # Use minimum size if label size is not yet determined
                    target_size = self.image_label.minimumSize()
                scaled_pixmap = pixmap.scaled(
                    target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.clear_preview()

        except Exception:
            self.clear_preview()

    def clear_preview(self):
        """Clear the preview"""
        self.image_label.clear()
        self.image_label.setText("No Preview")
        self.current_image_path = None

    def get_image_info(self, image_path: str) -> str:
        """Get image information text"""
        try:
            if not Path(image_path).exists():
                return "No image selected"

            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                return "Invalid image file"

            file_info = QFileInfo(image_path)
            size_mb = file_info.size() / (1024 * 1024)
            return f"{file_info.fileName()}\n{pixmap.width()}×{pixmap.height()}\n{size_mb:.1f} MB"

        except Exception as e:
            return f"Error: {str(e)}"


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
        layout.setSpacing(5)

        # Path input
        nav_layout = QHBoxLayout()

        path_label = QLabel("Path:")
        nav_layout.addWidget(path_label)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter directory path...")
        self.path_input.returnPressed.connect(self.on_path_input_entered)
        nav_layout.addWidget(self.path_input)

        goto_btn = QPushButton("Go")
        goto_btn.clicked.connect(self.on_path_input_entered)
        nav_layout.addWidget(goto_btn)

        layout.addLayout(nav_layout)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)

        # Directory tree view
        self.setup_tree_view()
        splitter.addWidget(self.tree_view)

        # Right side: image list, preview and info
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        # Ensure the right widget maintains its structure
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Image list (ratio 4)
        self.image_list = QListWidget()
        self.image_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_list.itemClicked.connect(self.on_image_item_clicked)
        self.image_list.itemDoubleClicked.connect(self.on_image_double_clicked)
        self.image_list.itemSelectionChanged.connect(self.on_image_selection_changed)
        # Install event filter for keyboard support
        self.image_list.installEventFilter(self)
        right_layout.addWidget(self.image_list, 4)

        # Image preview (ratio 4)
        self.image_preview = ImagePreviewWidget()
        self.image_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.image_preview, 4)

        # Image info (ratio 1)
        self.image_info_label = QLabel("No image selected")
        self.image_info_label.setFont(QFont("Arial", 9))
        self.image_info_label.setAlignment(Qt.AlignCenter)
        self.image_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.image_info_label.setMaximumHeight(80)  # Limit info area height
        self.image_info_label.setStyleSheet(
            "color: #666; border: 1px solid #ccc; background-color: #f9f9f9; padding: 5px;"
        )
        right_layout.addWidget(self.image_info_label, 1)

        splitter.addWidget(right_widget)

        # Set splitter ratios
        splitter.setStretchFactor(0, 1)  # Tree view
        splitter.setStretchFactor(1, 1)  # Image list and preview

        layout.addWidget(splitter)

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

                # Update path input
                self.path_input.setText(self.current_directory)

                # Update image list
                self.update_image_list()

        except Exception:
            pass  # Silently ignore errors

    def on_directory_selected(self, selected, deselected):
        """Handle directory selection in tree view"""
        try:
            indexes = selected.indexes()
            if indexes:
                index = indexes[0]
                directory_path = self.file_system_model.filePath(index)

                if directory_path != self.current_directory:
                    self.current_directory = directory_path
                    self.path_input.setText(self.current_directory)
                    self.update_image_list()

        except Exception:
            pass  # Silently ignore errors

    def update_image_list(self):
        """Update the list of images in current directory"""
        try:
            self.image_list.clear()
            # Clear preview and info when updating image list
            self.image_preview.clear_preview()
            self.image_info_label.setText("No image selected")

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

        except Exception:
            pass  # Silently ignore errors

    def on_image_item_clicked(self, item: QListWidgetItem):
        """Handle image item click"""
        try:
            image_path = item.data(Qt.UserRole)
            if image_path:
                # Show preview
                self.image_preview.set_image(image_path)
                # Update image info
                info_text = self.image_preview.get_image_info(image_path)
                self.image_info_label.setText(info_text)

        except Exception:
            pass  # Silently ignore errors

    def on_image_double_clicked(self, item: QListWidgetItem):
        """Handle image item double click"""
        try:
            image_path = item.data(Qt.UserRole)
            if image_path:
                # Emit signal to load image in main application
                self.image_selected.emit(image_path)
                pass  # Selection completed silently

        except Exception:
            pass  # Silently ignore errors

    def on_image_selection_changed(self):
        """Handle image selection change (for keyboard navigation)"""
        try:
            current_item = self.image_list.currentItem()
            if current_item:
                image_path = current_item.data(Qt.UserRole)
                if image_path:
                    # Show preview
                    self.image_preview.set_image(image_path)
                    # Update image info
                    info_text = self.image_preview.get_image_info(image_path)
                    self.image_info_label.setText(info_text)

        except Exception:
            pass  # Silently ignore errors

    def on_path_input_entered(self):
        """Handle path input when user presses Enter or clicks Go"""
        try:
            input_path = self.path_input.text().strip()
            if input_path:
                # Expand ~ to home directory
                if input_path.startswith("~"):
                    input_path = str(Path(input_path).expanduser())

                # Navigate to the entered path
                if Path(input_path).exists() and Path(input_path).is_dir():
                    self.navigate_to_directory(input_path)
                else:
                    pass  # Invalid path - do nothing silently

        except Exception:
            pass  # Silently ignore errors

    def get_current_image(self) -> str | None:
        """Get currently selected image path"""
        return self.image_preview.current_image_path

    def refresh(self):
        """Refresh current directory"""
        if self.current_directory:
            self.update_image_list()

    def eventFilter(self, source, event):
        """Event filter to handle keyboard events"""
        if source == self.image_list and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Return or key_event.key() == Qt.Key_Enter:
                # Handle Enter key - select current image
                current_item = self.image_list.currentItem()
                if current_item:
                    self.on_image_double_clicked(current_item)
                return True  # Event handled
        return super().eventFilter(source, event)
