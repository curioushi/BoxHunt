"""
File browser widget for selecting images
"""

from pathlib import Path

from PySide6.QtCore import (
    QDir,
    QEvent,
    QFileInfo,
    QSettings,
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
        self.project_manager = None  # Will be set by main window

        # Initialize QSettings
        self.settings = QSettings("BoxHunt", "BoxHuntConfig")

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
        # Enable context menu
        self.image_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.image_list.customContextMenuRequested.connect(self.show_context_menu)
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
        # Try to load last directory from settings
        last_directory = self.settings.value("file_browser_directory", "")

        if last_directory and Path(last_directory).exists():
            self.navigate_to_directory(last_directory)
        else:
            # Start in current working directory
            current_path = QDir.currentPath()
            if Path(current_path).exists():
                self.navigate_to_directory(current_path)
            else:
                # Fallback to home directory if current path doesn't exist
                self.navigate_to_directory(QDir.homePath())

    def navigate_to_directory(self, directory_path: str):
        """Navigate to specific directory"""
        try:
            path = Path(directory_path)
            if path.exists() and path.is_dir():
                self.current_directory = str(path)

                # Save directory to settings
                self.settings.setValue("file_browser_directory", self.current_directory)

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

            # Add to list with annotation status
            for image_file in image_files:
                item = QListWidgetItem(image_file.name)
                item.setData(Qt.UserRole, str(image_file))
                item.setToolTip(str(image_file))

                # Set annotation status if project manager is available
                if self.project_manager and self.project_manager.is_project_open():
                    self.set_item_annotation_status(item, image_file.name)

                self.image_list.addItem(item)

        except Exception:
            pass  # Silently ignore errors

    def set_item_annotation_status(self, item: QListWidgetItem, filename: str):
        """Set the annotation status for a list item"""
        try:
            if not self.project_manager:
                return

            image_info = self.project_manager.get_image_info(filename)

            # If image is not in database, it needs annotation by default
            if not image_info:
                # Default: needs annotation, not annotated
                needs_annotation = True
                is_annotated = False
            else:
                needs_annotation = image_info["needs_annotation"]
                is_annotated = image_info["is_annotated"]

            # Set text color based on needs_annotation
            if not needs_annotation:
                item.setForeground(Qt.gray)

            # Add checkmark for annotated images
            if is_annotated:
                item.setText(f"✓ {filename}")

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

    def next_image(self):
        """Go to next image in the list, skipping images that don't need annotation"""
        try:
            current_row = self.image_list.currentRow()
            next_row = current_row + 1

            # Find next image that needs annotation
            while next_row < self.image_list.count():
                item = self.image_list.item(next_row)
                if item and self._image_needs_annotation(item):
                    self.image_list.setCurrentRow(next_row)
                    self.on_image_double_clicked(item)
                    return
                next_row += 1

            # If no more images need annotation, stay at current position
            if current_row < self.image_list.count() - 1:
                # Move to the last image even if it doesn't need annotation
                self.image_list.setCurrentRow(self.image_list.count() - 1)
                current_item = self.image_list.currentItem()
                if current_item:
                    self.on_image_double_clicked(current_item)
        except Exception:
            pass

    def previous_image(self):
        """Go to previous image in the list, skipping images that don't need annotation"""
        try:
            current_row = self.image_list.currentRow()
            prev_row = current_row - 1

            # Find previous image that needs annotation
            while prev_row >= 0:
                item = self.image_list.item(prev_row)
                if item and self._image_needs_annotation(item):
                    self.image_list.setCurrentRow(prev_row)
                    self.on_image_double_clicked(item)
                    return
                prev_row -= 1

            # If no previous images need annotation, stay at current position
            if current_row > 0:
                # Move to the first image even if it doesn't need annotation
                self.image_list.setCurrentRow(0)
                current_item = self.image_list.currentItem()
                if current_item:
                    self.on_image_double_clicked(current_item)
        except Exception:
            pass

    def get_current_image_index(self) -> int:
        """Get current image index in the list"""
        return self.image_list.currentRow()

    def get_image_count(self) -> int:
        """Get total number of images in the list"""
        return self.image_list.count()

    def set_current_image(self, image_path: str):
        """Set current image in the list"""
        try:
            if not image_path:
                return

            # Find the item with matching image path
            for i in range(self.image_list.count()):
                item = self.image_list.item(i)
                if item and item.data(Qt.UserRole) == image_path:
                    self.image_list.setCurrentRow(i)
                    # Update preview and info
                    self.image_preview.set_image(image_path)
                    info_text = self.image_preview.get_image_info(image_path)
                    self.image_info_label.setText(info_text)
                    break
        except Exception:
            pass

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

    def set_project_manager(self, project_manager):
        """Set the project manager for annotation status"""
        self.project_manager = project_manager

    def get_image_files(self) -> list:
        """Get list of image filenames in current directory"""
        try:
            if not self.current_directory:
                return []

            directory = Path(self.current_directory)
            if not directory.exists():
                return []

            image_files = []
            for ext in self.supported_formats:
                pattern = f"*{ext}"
                image_files.extend([f.name for f in directory.glob(pattern)])
                pattern = f"*{ext.upper()}"
                image_files.extend([f.name for f in directory.glob(pattern)])

            return sorted(image_files, key=str.lower)

        except Exception:
            return []

    def clear_image_list(self):
        """Clear the image list"""
        self.image_list.clear()
        self.image_preview.clear_preview()
        self.image_info_label.setText("No image selected")

    def refresh_annotation_status(self):
        """Refresh annotation status for all items"""
        try:
            for i in range(self.image_list.count()):
                item = self.image_list.item(i)
                if item:
                    filename = item.data(Qt.UserRole)
                    if filename:
                        filename = Path(filename).name
                        self.set_item_annotation_status(item, filename)
        except Exception:
            pass  # Silently ignore errors

    def show_context_menu(self, position):
        """Show context menu for image list items"""
        try:
            if not self.project_manager or not self.project_manager.is_project_open():
                return

            item = self.image_list.itemAt(position)
            if not item:
                return

            filename = Path(item.data(Qt.UserRole)).name
            image_info = self.project_manager.get_image_info(filename)

            if not image_info:
                return

            from PySide6.QtWidgets import QMenu

            menu = QMenu(self)

            # Toggle annotation need
            needs_annotation = image_info["needs_annotation"]
            toggle_action = menu.addAction("Toggle Annotation")

            # Store the current values to avoid closure issues
            current_filename = filename
            new_status = not needs_annotation
            toggle_action.triggered.connect(
                lambda: self.toggle_annotation_status(current_filename, new_status)
            )

            menu.exec(self.image_list.mapToGlobal(position))

        except Exception:
            pass  # Silently ignore errors

    def toggle_annotation_status(self, filename: str, needs_annotation: bool):
        """Toggle annotation status for an image"""
        try:
            if self.project_manager.set_image_annotation_status(
                filename, needs_annotation
            ):
                # Refresh the item display
                for i in range(self.image_list.count()):
                    item = self.image_list.item(i)
                    if item and Path(item.data(Qt.UserRole)).name == filename:
                        # Reset the item text first (remove checkmark if present)
                        original_text = Path(item.data(Qt.UserRole)).name
                        item.setText(original_text)
                        # Reset foreground color
                        item.setForeground(Qt.black)
                        # Set the correct status
                        self.set_item_annotation_status(item, filename)
                        break
        except Exception:
            pass  # Silently ignore errors

    def _image_needs_annotation(self, item: QListWidgetItem) -> bool:
        """Check if an image needs annotation based on its item"""
        try:
            if not self.project_manager:
                return True  # Default to needing annotation if no project manager

            image_path = item.data(Qt.UserRole)
            if not image_path:
                return True

            filename = Path(image_path).name
            image_info = self.project_manager.get_image_info(filename)

            # If image is not in database, it needs annotation by default
            if not image_info:
                return True

            return image_info.get("needs_annotation", True)
        except Exception:
            return True  # Default to needing annotation on error
