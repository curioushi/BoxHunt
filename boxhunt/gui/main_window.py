"""
Main window for BoxHunt 3D box creation tool
"""

import os
from pathlib import Path

import imagehash
from PIL import Image
from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .box3d_viewer import Box3DViewerWidget
from .classification import (
    ClassificationUrlDialog,
    check_healthy,
    classify_single_image,
)
from .crop_preview import CropPreviewWidget
from .export_dialog import ExportDialog
from .file_browser import FileBrowserWidget
from .image_annotation import ImageAnnotationWidget
from .log_widget import LogWidget
from .logger import logger
from .project_manager import ProjectManager


class BoxMakerMainWindow(QMainWindow):
    """Main application window"""

    # Signals
    image_loaded = Signal(str)  # image_path

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_image_path = None

        # Initialize QSettings
        self.settings = QSettings("BoxHunt", "BoxHuntConfig")

        # Load last project directory from settings
        self.last_project_directory = self.settings.value(
            "last_project_directory", os.getcwd()
        )

        # Load crop preview visibility from settings
        self.crop_preview_visible = self.settings.value(
            "crop_preview_visible", True, type=bool
        )

        # Initialize project manager
        self.project_manager = ProjectManager(self)

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

        # Store reference to top splitter for crop preview visibility control
        self.top_splitter = top_splitter

        # Apply initial crop preview visibility
        if not self.crop_preview_visible:
            self.crop_preview.hide()

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

        # Project management
        create_project_action = QAction("Create Project", self)
        create_project_action.triggered.connect(self.create_project)
        file_menu.addAction(create_project_action)

        open_project_action = QAction("Open Project", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(open_project_action)

        close_project_action = QAction("Close Project", self)
        close_project_action.triggered.connect(self.close_project)
        file_menu.addAction(close_project_action)

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        # Show Crop Preview toggle
        self.show_crop_preview_action = QAction("Show Crop Preview", self)
        self.show_crop_preview_action.setCheckable(True)
        self.show_crop_preview_action.setChecked(self.crop_preview_visible)
        self.show_crop_preview_action.triggered.connect(self.toggle_crop_preview)
        view_menu.addAction(self.show_crop_preview_action)

    def create_toolbar(self):
        """Create toolbar"""
        toolbar = QToolBar()
        self.addToolBar(toolbar)

        # Project management buttons
        create_project_action = QAction("New Project", self)
        create_project_action.setToolTip("Create new annotation project")
        create_project_action.triggered.connect(self.create_project)
        toolbar.addAction(create_project_action)

        open_project_action = QAction("Open Project", self)
        open_project_action.setToolTip("Open existing annotation project")
        open_project_action.triggered.connect(self.open_project)
        toolbar.addAction(open_project_action)

        toolbar.addSeparator()

        # Submit annotation button
        submit_action = QAction("Submit", self)
        submit_action.setShortcut("Ctrl+Return")
        submit_action.setToolTip("Save annotation and go to next image (Ctrl+Enter)")
        submit_action.triggered.connect(self.submit_annotation)
        toolbar.addAction(submit_action)

        toolbar.addSeparator()

        # Classify all images button
        classify_action = QAction("Classify All", self)
        classify_action.setShortcut("Ctrl+C")
        classify_action.setToolTip(
            "Classify all images with AI and update annotation status"
        )
        classify_action.triggered.connect(self.classify_all_images)
        toolbar.addAction(classify_action)

        # Export all annotations button
        export_action = QAction("Export All", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setToolTip("Export all annotations with progress")
        export_action.triggered.connect(self.export_all_annotations)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        # Navigation shortcuts
        next_image_action = QAction("Next Image", self)
        next_image_action.setShortcut("Ctrl+N")
        next_image_action.setToolTip("Go to next image (Ctrl+N)")
        next_image_action.triggered.connect(self.next_image)
        toolbar.addAction(next_image_action)

        skip_image_action = QAction("Skip Image", self)
        skip_image_action.setShortcut("Ctrl+M")
        skip_image_action.setToolTip("Mark as skip and go to next image (Ctrl+M)")
        skip_image_action.triggered.connect(self.skip_current_image)
        toolbar.addAction(skip_image_action)

        prev_image_action = QAction("Previous Image", self)
        prev_image_action.setShortcut("Ctrl+P")
        prev_image_action.setToolTip("Go to previous image (Ctrl+P)")
        prev_image_action.triggered.connect(self.previous_image)
        toolbar.addAction(prev_image_action)

        toolbar.addSeparator()

        # Rename images with pHash button
        rename_images_action = QAction("Rename Images with pHash", self)
        rename_images_action.setToolTip(
            "Rename images using color hash and average hash"
        )
        rename_images_action.triggered.connect(self.rename_images_with_hash)
        toolbar.addAction(rename_images_action)

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

        # Connect project manager signals
        self.project_manager.project_opened.connect(self.on_project_opened)
        self.project_manager.project_closed.connect(self.on_project_closed)
        self.project_manager.annotation_saved.connect(self.on_annotation_saved)
        self.project_manager.annotation_loaded.connect(self.on_annotation_loaded)

        # Set project manager in file browser
        self.file_browser.set_project_manager(self.project_manager)

    def create_project(self):
        """Create a new annotation project"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Project Directory",
            self.last_project_directory,
        )

        if directory:
            if self.project_manager.create_project(directory):
                # Save last project directory to settings
                self.last_project_directory = directory
                self.settings.setValue("last_project_directory", directory)
                self.status_bar.showMessage(f"Created project: {directory}")

    def open_project(self):
        """Open an existing annotation project"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Project Directory",
            self.last_project_directory,
        )

        if directory:
            if self.project_manager.open_project(directory):
                # Save last project directory to settings
                self.last_project_directory = directory
                self.settings.setValue("last_project_directory", directory)
                self.status_bar.showMessage(f"Opened project: {directory}")

    def close_project(self):
        """Close current project"""
        if self.project_manager.is_project_open():
            self.project_manager.close_project()
            self.status_bar.showMessage("Project closed")
        else:
            QMessageBox.information(self, "No Project", "No project is currently open.")

    def on_project_opened(self, project_path: str):
        """Handle project opened event"""
        # Switch file browser to project directory
        self.file_browser.navigate_to_directory(project_path)

        # Update project database with current image files
        image_files = self.file_browser.get_image_files()
        if image_files:
            self.project_manager.update_image_list(image_files)

        # Refresh annotation status in file browser
        self.file_browser.refresh_annotation_status()

        # Update window title
        self.setWindowTitle(f"BoxHunt - {Path(project_path).name}")

    def on_project_closed(self):
        """Handle project closed event"""
        # Clear current image
        self.current_image_path = None
        self.image_annotation.clear_annotations()
        self.box3d_viewer.clear_all_textures()

        # Reset window title
        self.setWindowTitle("BoxHunt - 3D Box Creation Tool")

        # Clear file browser
        self.file_browser.clear_image_list()

    def on_annotation_saved(self, filename: str):
        """Handle annotation saved event"""
        self.status_bar.showMessage(f"Annotation saved for: {filename}")
        # Refresh annotation status in file browser
        self.file_browser.refresh_annotation_status()

    def on_annotation_loaded(self, filename: str):
        """Handle annotation loaded event"""
        self.status_bar.showMessage(f"Annotation loaded for: {filename}")

    def submit_annotation(self):
        """Save current annotation and go to next image"""
        if not self.project_manager.is_project_open():
            QMessageBox.warning(self, "Warning", "No project is currently open.")
            return

        if not self.current_image_path:
            QMessageBox.warning(self, "Warning", "No image is currently loaded.")
            return

        # Get current annotation data
        annotations = self.image_annotation.get_annotations()
        if not annotations:
            QMessageBox.warning(self, "Warning", "No annotations to save.")
            return

        # Build complete annotation data (without crops to save space)
        annotation_data = {
            "annotations": annotations,
            "box_dimensions": {
                "width": self.box3d_viewer.renderer.box_width,
                "height": self.box3d_viewer.renderer.box_height,
                "length": self.box3d_viewer.renderer.box_depth,
            },
        }

        # Save annotation
        filename = Path(self.current_image_path).name
        if self.project_manager.save_annotation(filename, annotation_data):
            # Go to next image
            self.next_image()
        else:
            QMessageBox.critical(self, "Error", "Failed to save annotation.")

    def skip_current_image(self):
        """Mark current image as skip and go to next image"""
        if not self.project_manager.is_project_open():
            QMessageBox.warning(self, "Warning", "No project is currently open.")
            return

        if not self.current_image_path:
            QMessageBox.warning(self, "Warning", "No image is currently loaded.")
            return

        # Mark current image as not needing annotation
        filename = Path(self.current_image_path).name
        if self.project_manager.set_image_annotation_status(filename, False):
            self.status_bar.showMessage(f"Marked {filename} as skip")
            # Refresh annotation status in file browser
            self.file_browser.refresh_annotation_status()
            # Go to next image
            self.next_image()
        else:
            QMessageBox.critical(self, "Error", "Failed to mark image as skip.")

    def export_all_annotations(self):
        """Export all annotations using the export dialog"""
        if not self.project_manager.is_project_open():
            QMessageBox.warning(self, "Warning", "No project is currently open.")
            return

        dialog = ExportDialog(self.project_manager, self)
        dialog.exec()

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

            # Set current image in file browser
            self.file_browser.set_current_image(image_path)

            # Load annotation if project is open
            if self.project_manager.is_project_open():
                filename = Path(image_path).name
                annotation_data = self.project_manager.load_annotation(filename)
                if annotation_data:
                    self.load_annotation_data(annotation_data)

            self.status_bar.showMessage(f"Loaded: {Path(image_path).name}")
            logger.info(f"Image loaded: {image_path}")
            self.image_loaded.emit(image_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {str(e)}")
            logger.error(f"Error loading image: {str(e)}")

    def load_annotation_data(self, annotation_data: dict):
        """Load annotation data into the interface"""
        try:
            # Load annotations first
            if "annotations" in annotation_data:
                self.image_annotation.load_annotations(annotation_data["annotations"])

            # Load box dimensions
            if "box_dimensions" in annotation_data:
                dims = annotation_data["box_dimensions"]
                self.box3d_viewer.renderer.set_box_dimensions(
                    dims.get("width", 1.0),
                    dims.get("height", 1.0),
                    dims.get("length", 1.0),
                )

            # Force update crop preview and 3D viewer
            # The crop_preview should be updated automatically via signal connection,
            # but we'll also trigger it manually to ensure it works
            annotations = self.image_annotation.get_annotations()
            if annotations:
                self.crop_preview.update_crops(annotations)

        except Exception as e:
            logger.error(f"Failed to load annotation data: {str(e)}")

    def next_image(self):
        """Go to next image"""
        self.file_browser.next_image()

    def previous_image(self):
        """Go to previous image"""
        self.file_browser.previous_image()

    def toggle_crop_preview(self):
        """Toggle crop preview visibility"""
        visible = self.show_crop_preview_action.isChecked()
        self.crop_preview_visible = visible

        if visible:
            self.crop_preview.show()
        else:
            self.crop_preview.hide()

        # Save setting
        self.settings.setValue("crop_preview_visible", visible)

    def rename_images_with_hash(self):
        """Rename images in a directory using color hash and average hash"""
        # Select directory containing images
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Directory with Images",
            self.last_project_directory,
        )

        if not directory:
            return

        try:
            directory_path = Path(directory)
            image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

            # Find all image files
            image_files = []
            for ext in image_extensions:
                image_files.extend(directory_path.glob(f"*{ext}"))
                image_files.extend(directory_path.glob(f"*{ext.upper()}"))

            if not image_files:
                QMessageBox.warning(
                    self,
                    "No Images Found",
                    f"No image files found in directory: {directory}",
                )
                return

            # Confirm with user
            reply = QMessageBox.question(
                self,
                "Confirm Rename",
                f"Found {len(image_files)} images. This will rename all images to format: {{color_hash}}_{{average_hash}}.{{original_extension}}\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            renamed_count = 0
            failed_count = 0
            skipped_count = 0

            # Create progress dialog
            progress = QProgressDialog(
                "Renaming images...", "Cancel", 0, len(image_files), self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(False)
            progress.setAutoReset(False)

            for i, image_file in enumerate(image_files):
                # Update progress
                progress.setValue(i)
                progress.setLabelText(f"Processing: {image_file.name}")

                # Check if user cancelled
                if progress.wasCanceled():
                    logger.info("Image renaming cancelled by user")
                    break

                try:
                    # Open image for hash calculation only
                    with Image.open(image_file) as img:
                        # Calculate hashes
                        color_hash = imagehash.colorhash(img, binbits=3)
                        average_hash = imagehash.average_hash(img, hash_size=8)

                    # Get original file extension
                    original_extension = image_file.suffix.lower()

                    # Create new filename with original extension
                    new_filename = f"{color_hash}_{average_hash}{original_extension}"
                    new_path = image_file.parent / new_filename

                    # Skip if filename already exists
                    if new_path.exists():
                        logger.warning(
                            f"Skipped {image_file.name}: target filename {new_filename} already exists"
                        )
                        skipped_count += 1
                        continue

                    # Move file using OS move operation
                    image_file.rename(new_path)

                    renamed_count += 1
                    logger.info(f"Renamed: {image_file.name} -> {new_path.name}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to rename {image_file.name}: {str(e)}")

            # Close progress dialog
            progress.setValue(len(image_files))
            progress.close()

            # Show results
            if progress.wasCanceled():
                message = f"Operation cancelled. Renamed {renamed_count} images"
                if skipped_count > 0:
                    message += f"\nSkipped {skipped_count} images (duplicate filenames)"
                if failed_count > 0:
                    message += f"\nFailed to rename {failed_count} images"

                QMessageBox.information(self, "Operation Cancelled", message)
                self.status_bar.showMessage(
                    f"Cancelled: Renamed {renamed_count} images in {directory}"
                )
            elif renamed_count > 0:
                message = f"Successfully renamed {renamed_count} images"
                if skipped_count > 0:
                    message += f"\nSkipped {skipped_count} images (duplicate filenames)"
                if failed_count > 0:
                    message += f"\nFailed to rename {failed_count} images"

                QMessageBox.information(self, "Rename Complete", message)
                self.status_bar.showMessage(
                    f"Renamed {renamed_count} images in {directory}"
                )
            else:
                message = "No images were renamed"
                if skipped_count > 0:
                    message += f"\nSkipped {skipped_count} images (duplicate filenames)"
                if failed_count > 0:
                    message += f"\nFailed to rename {failed_count} images"

                QMessageBox.warning(self, "Rename Failed", message)

        except Exception as e:
            error_msg = f"Failed to rename images: {str(e)}"
            QMessageBox.critical(self, "Rename Error", error_msg)
            logger.error(error_msg)

    def classify_all_images(self):
        """Classify all images in the current project using AI and update annotation status"""
        # Check if project is open
        if not self.project_manager.is_project_open():
            QMessageBox.warning(
                self,
                "No Project Open",
                "Please open a project first before classifying images.",
            )
            return

        # Get project directory
        project_dir = self.project_manager.get_project_path()
        if not project_dir:
            QMessageBox.warning(
                self, "No Project Directory", "Unable to get project directory."
            )
            return

        try:
            # Get classification server URL from settings
            server_url = self.settings.value(
                "classification_server_url", "http://localhost:22335"
            )

            # Check server health
            if not check_healthy(server_url):
                # Show URL configuration dialog
                dialog = ClassificationUrlDialog(
                    server_url.replace("http://", "").replace("https://", ""), self
                )
                if dialog.exec() == QDialog.Accepted:
                    server_url = dialog.get_url()
                    # Save new URL to settings
                    self.settings.setValue("classification_server_url", server_url)
                    self.settings.sync()
                else:
                    return  # User cancelled

                # Check health again with new URL
                if not check_healthy(server_url):
                    QMessageBox.critical(
                        self,
                        "Server Connection Failed",
                        f"Unable to connect to classification server at {server_url}\n\nPlease check if the server is running.",
                    )
                    return

            # Get all image files from project
            image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
            image_files = []

            for ext in image_extensions:
                image_files.extend(Path(project_dir).glob(f"*{ext}"))
                image_files.extend(Path(project_dir).glob(f"*{ext.upper()}"))

            if not image_files:
                QMessageBox.warning(
                    self,
                    "No Images Found",
                    f"No image files found in project directory: {project_dir}",
                )
                return

            classified_count = 0
            failed_count = 0
            needs_annotation_count = 0
            skip_annotation_count = 0

            # Create progress dialog
            progress = QProgressDialog(
                "Classifying images...", "Cancel", 0, len(image_files), self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(False)
            progress.setAutoReset(False)

            for i, image_file in enumerate(image_files):
                # Update progress
                progress.setValue(i)
                progress.setLabelText(f"Classifying: {image_file.name}")

                # Check if user cancelled
                if progress.wasCanceled():
                    logger.info("Image classification cancelled by user")
                    break

                try:
                    # Classify the image
                    result = classify_single_image(str(image_file), server_url)

                    if result:
                        # Get classification result
                        class_id = result.get("class_id", 0)
                        confidence = result.get("confidence", 0.0)

                        # Determine annotation status based on class_id
                        # class_id = 1 means needs annotation
                        needs_annotation = class_id == 1

                        # Update database
                        filename = image_file.name
                        if self.project_manager.set_image_annotation_status(
                            filename, needs_annotation
                        ):
                            classified_count += 1
                            if needs_annotation:
                                needs_annotation_count += 1
                            else:
                                skip_annotation_count += 1

                            logger.info(
                                f"Classified {filename}: class_id={class_id}, confidence={confidence:.3f}, needs_annotation={needs_annotation}"
                            )
                        else:
                            failed_count += 1
                            logger.error(f"Failed to update database for {filename}")
                    else:
                        failed_count += 1
                        logger.error(f"Classification failed for {image_file.name}")

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to classify {image_file.name}: {str(e)}")

            # Close progress dialog
            progress.setValue(len(image_files))
            progress.close()

            # Refresh file browser to show updated status
            if hasattr(self, "file_browser") and self.file_browser:
                self.file_browser.refresh_annotation_status()

            # Show results
            if progress.wasCanceled():
                message = f"Operation cancelled. Classified {classified_count} images"
                if needs_annotation_count > 0:
                    message += f"\n{needs_annotation_count} images marked as needing annotation"
                if skip_annotation_count > 0:
                    message += (
                        f"\n{skip_annotation_count} images marked as skip annotation"
                    )
                if failed_count > 0:
                    message += f"\nFailed to classify {failed_count} images"

                QMessageBox.information(self, "Operation Cancelled", message)
                self.status_bar.showMessage(
                    f"Cancelled: Classified {classified_count} images in {project_dir}"
                )
            elif classified_count > 0:
                message = f"Successfully classified {classified_count} images"
                if needs_annotation_count > 0:
                    message += f"\n{needs_annotation_count} images marked as needing annotation"
                if skip_annotation_count > 0:
                    message += (
                        f"\n{skip_annotation_count} images marked as skip annotation"
                    )
                if failed_count > 0:
                    message += f"\nFailed to classify {failed_count} images"

                QMessageBox.information(self, "Classification Complete", message)
                self.status_bar.showMessage(
                    f"Classified {classified_count} images in {project_dir}"
                )
            else:
                message = "No images were classified"
                if failed_count > 0:
                    message += f"\nFailed to classify {failed_count} images"

                QMessageBox.warning(self, "Classification Failed", message)

        except Exception as e:
            error_msg = f"Failed to classify images: {str(e)}"
            QMessageBox.critical(self, "Classification Error", error_msg)
            logger.error(error_msg)
