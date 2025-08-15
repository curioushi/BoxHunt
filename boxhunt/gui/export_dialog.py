"""
Export dialog for batch exporting all annotations
"""

import json
import shutil
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .logger import logger
from .utils import apply_perspective_transform


class ExportWorker(QThread):
    """Worker thread for exporting annotations"""

    progress_updated = Signal(int, str)  # progress, filename
    export_finished = Signal(bool, str)  # success, message

    def __init__(self, annotations_data, project_path, output_dir, parent=None):
        super().__init__(parent)
        self.annotations_data = annotations_data
        self.project_path = project_path
        self.output_dir = output_dir

    def run(self):
        """Run the export process"""
        try:
            project_dir = Path(self.project_path)
            output_path = Path(self.output_dir)

            if not output_path.exists():
                output_path.mkdir(parents=True, exist_ok=True)

            total_annotations = len(self.annotations_data)
            exported_count = 0
            failed_count = 0

            for i, annotation_item in enumerate(self.annotations_data):
                filename = annotation_item["filename"]
                annotation = annotation_item["annotation"]

                # Update progress
                self.progress_updated.emit(i, f"Exporting: {filename}")

                try:
                    # Create subdirectory for this image
                    image_name = Path(filename).stem
                    image_export_dir = output_path / image_name

                    if image_export_dir.exists():
                        shutil.rmtree(image_export_dir)

                    image_export_dir.mkdir(parents=True, exist_ok=True)

                    # Copy original image
                    original_image_path = project_dir / filename
                    if original_image_path.exists():
                        origin_path = image_export_dir / "origin.jpg"
                        shutil.copy2(original_image_path, origin_path)

                    # Export annotation data
                    data_path = image_export_dir / "data.json"
                    with open(data_path, "w", encoding="utf-8") as f:
                        json.dump(annotation, f, indent=2, ensure_ascii=False)

                    # Generate and export textures from annotations
                    self._generate_and_export_textures(
                        annotation, original_image_path, image_export_dir
                    )

                    exported_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to export {filename}: {str(e)}")

            # Final progress update
            self.progress_updated.emit(total_annotations, "Export completed")

            # Generate summary
            message = "Export completed!\n\n"
            message += f"Successfully exported: {exported_count} annotations\n"
            if failed_count > 0:
                message += f"Failed to export: {failed_count} annotations\n"
            message += f"Output directory: {self.output_dir}"

            self.export_finished.emit(True, message)

        except Exception as e:
            error_msg = f"Export failed: {str(e)}"
            logger.error(error_msg)
            self.export_finished.emit(False, error_msg)

    def _generate_and_export_textures(
        self, annotation_data, original_image_path, export_dir
    ):
        """Generate and export textures from annotations"""
        try:
            # Load original image
            original_image = Image.open(original_image_path)
            if original_image.mode not in ["RGB", "RGBA"]:
                original_image = original_image.convert("RGB")

            # Get annotations
            annotations = annotation_data.get("annotations", [])
            if not annotations:
                return

            # Build available textures mapping
            available_textures = {}
            for annotation in annotations:
                if (
                    annotation.get("type") == "polygon"
                    and len(annotation.get("points", [])) == 4
                ):
                    label = annotation.get("label", "").lower()
                    points = annotation.get("points", [])

                    # Apply perspective transformation to get 512x512 rectified image
                    crop_region = apply_perspective_transform(
                        original_image, points, output_size=(512, 512)
                    )
                    available_textures[label] = crop_region

            # Get fallback mapping (same as in main window)
            fallback_map = {
                "front": ["back", "left", "right", "top", "bottom"],
                "back": ["front", "right", "left", "top", "bottom"],
                "left": ["right", "front", "back", "top", "bottom"],
                "right": ["left", "back", "front", "top", "bottom"],
                "top": ["bottom", "front", "back", "left", "right"],
                "bottom": ["top", "front", "back", "left", "right"],
            }

            face_names = ["front", "back", "left", "right", "top", "bottom"]

            # Export each face with fallback strategy
            for face_name in face_names:
                texture_image = None

                # Try to get texture for this face
                if face_name in available_textures:
                    texture_image = available_textures[face_name]
                else:
                    # Apply fallback strategy
                    for fallback_face in fallback_map[face_name]:
                        if fallback_face in available_textures:
                            texture_image = available_textures[fallback_face]
                            break

                # Export the texture if available
                if texture_image:
                    output_path = export_dir / f"{face_name}.jpg"
                    # Convert RGBA to RGB for JPEG compatibility
                    if texture_image.mode == "RGBA":
                        # Create white background
                        rgb_image = Image.new(
                            "RGB", texture_image.size, (255, 255, 255)
                        )
                        rgb_image.paste(texture_image, mask=texture_image.split()[-1])
                        rgb_image.save(output_path, "JPEG", quality=95)
                    else:
                        texture_image.save(output_path, "JPEG", quality=95)

        except Exception as e:
            logger.error(f"Failed to generate and export textures: {str(e)}")


class ExportDialog(QDialog):
    """Dialog for exporting all annotations"""

    def __init__(self, project_manager, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.export_worker = None

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Setup user interface"""
        self.setWindowTitle("Export All Annotations")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Project info
        info_group = QGroupBox("Project Information")
        info_layout = QFormLayout(info_group)

        project_path = self.project_manager.get_project_path() or "No project open"
        self.project_path_label = QLabel(project_path)
        info_layout.addRow("Project Path:", self.project_path_label)

        stats = self.project_manager.get_project_statistics()
        self.stats_label = QLabel(
            f"Total: {stats.get('total_images', 0)}, "
            f"Annotated: {stats.get('annotated_images', 0)}, "
            f"Actual Annotations: {stats.get('actual_annotated_images', 0)}, "
            f"Completion: {stats.get('completion_rate', 0):.1f}%"
        )
        info_layout.addRow("Statistics:", self.stats_label)

        layout.addWidget(info_group)

        # Export options
        options_group = QGroupBox("Export Options")
        options_layout = QFormLayout(options_group)

        self.output_dir_label = QLabel("Select output directory...")
        self.select_dir_btn = QPushButton("Browse...")
        options_layout.addRow("Output Directory:", self.output_dir_label)
        options_layout.addRow("", self.select_dir_btn)

        layout.addWidget(options_group)

        # Progress
        progress_group = QGroupBox("Export Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to export")
        progress_layout.addWidget(self.status_label)

        layout.addWidget(progress_group)

        # Log
        log_group = QGroupBox("Export Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self.validate_annotations)

        self.export_btn = QPushButton("Export")
        self.export_btn.setDefault(True)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.validate_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def setup_connections(self):
        """Setup signal connections"""
        self.select_dir_btn.clicked.connect(self.select_output_directory)
        self.export_btn.clicked.connect(self.start_export)

    def select_output_directory(self):
        """Select output directory for export"""
        current_dir = self.output_dir_label.text()
        if current_dir == "Select output directory...":
            current_dir = ""

        directory = QFileDialog.getExistingDirectory(
            self, "Select Export Directory", current_dir
        )

        if directory:
            self.output_dir_label.setText(directory)

    def start_export(self):
        """Start the export process"""
        if not self.project_manager.is_project_open():
            QMessageBox.warning(self, "Warning", "No project is currently open.")
            return

        output_dir = self.output_dir_label.text()
        if output_dir == "Select output directory...":
            QMessageBox.warning(self, "Warning", "Please select an output directory.")
            return

        # Get all annotations
        annotations_data = self.project_manager.get_all_annotations()
        if not annotations_data:
            QMessageBox.information(self, "No Data", "No annotations found to export.")
            return

        # Start export
        self.export_btn.setEnabled(False)
        self.select_dir_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(annotations_data))
        self.progress_bar.setValue(0)

        self.log_text.clear()
        self.log_text.append(
            f"Starting export of {len(annotations_data)} annotations..."
        )

        # Create and start worker thread
        self.export_worker = ExportWorker(
            annotations_data, self.project_manager.get_project_path(), output_dir, self
        )

        self.export_worker.progress_updated.connect(self.update_progress)
        self.export_worker.export_finished.connect(self.export_finished)
        self.export_worker.start()

    def update_progress(self, value, status):
        """Update progress bar and status"""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
        self.log_text.append(status)

    def export_finished(self, success, message):
        """Handle export completion"""
        self.export_btn.setEnabled(True)
        self.select_dir_btn.setEnabled(True)

        if success:
            QMessageBox.information(self, "Export Complete", message)
            self.log_text.append("Export completed successfully!")
        else:
            QMessageBox.critical(self, "Export Failed", message)
            self.log_text.append(f"Export failed: {message}")

        # Clean up worker
        if self.export_worker:
            self.export_worker.deleteLater()
            self.export_worker = None

    def validate_annotations(self):
        """Validate all annotation results"""
        if not self.project_manager.is_project_open():
            QMessageBox.warning(self, "Warning", "No project is currently open.")
            return

        # Get all annotations
        annotations_data = self.project_manager.get_all_annotations()
        if not annotations_data:
            QMessageBox.information(
                self, "No Data", "No annotations found to validate."
            )
            return

        self.log_text.append("Starting annotation validation...")

        validation_errors = []

        for item in annotations_data:
            filename = item["filename"]
            annotation = item["annotation"]

            errors = self._validate_single_annotation(filename, annotation)
            if errors:
                validation_errors.extend(errors)

        # Report results
        if validation_errors:
            self.log_text.append(
                f"\nValidation completed with {len(validation_errors)} errors:"
            )
            for error in validation_errors:
                self.log_text.append(f"  - {error}")
        else:
            self.log_text.append(
                "\nValidation completed successfully! All annotations are valid."
            )

        self.log_text.append("Validation finished.")

    def _validate_single_annotation(
        self, filename: str, annotation_data: dict
    ) -> list[str]:
        """Validate a single annotation and return list of errors"""
        errors = []

        # Get annotations list
        annotations = annotation_data.get("annotations", [])
        if not annotations:
            errors.append(f"{filename}: No annotations found")
            return errors

        # Check for required labels
        labels = [
            ann.get("label", "").lower()
            for ann in annotations
            if ann.get("type") == "polygon"
        ]

        # Check for top and front (required)
        if "top" not in labels:
            errors.append(f"{filename}: Missing 'top' annotation")
        if "front" not in labels:
            errors.append(f"{filename}: Missing 'front' annotation")

        # Check for left or right (at least one required)
        if "left" not in labels and "right" not in labels:
            errors.append(
                f"{filename}: Missing both 'left' and 'right' annotations (need at least one)"
            )

        # Find top annotation to check p2.y vs p4.y
        top_annotation = None
        for ann in annotations:
            if ann.get("label", "").lower() == "top" and ann.get("type") == "polygon":
                top_annotation = ann
                break

        if top_annotation:
            points = top_annotation.get("points", [])
            if len(points) == 4:
                sorted_points_y = sorted(points, key=lambda x: x[1])
                pa = sorted_points_y[0]
                pb = sorted_points_y[-1]
                pa_x = pa[0]
                pb_x = pb[0]

                # Check pa.x vs pb.x and required side annotation
                if pa_x < pb_x:
                    if "right" not in labels:
                        errors.append(
                            f"{filename}: pa_x < pb_x but missing 'right' annotation"
                        )
                elif pa_x > pb_x:
                    if "left" not in labels:
                        errors.append(
                            f"{filename}: pa_x > pb_x but missing 'left' annotation"
                        )

        # Check annotation order for front, left/right
        for label in ["front", "left", "right"]:
            if label in labels:
                for ann in annotations:
                    if (
                        ann.get("label", "").lower() == label
                        and ann.get("type") == "polygon"
                    ):
                        points = ann.get("points", [])
                        if len(points) >= 4:
                            p1, p2, p3, p4 = points[:4]

                            # Check p1.x < p2.x
                            if p1[1] >= p2[1]:
                                errors.append(
                                    f"{filename}: {label} annotation - p1.x >= p2.x (should be <)"
                                )

                            # Check p4.x < p3.x
                            if p4[1] >= p3[1]:
                                errors.append(
                                    f"{filename}: {label} annotation - p4.x >= p3.x (should be <)"
                                )

                            # Check p1.y < p4.y
                            if p1[0] >= p4[0]:
                                errors.append(
                                    f"{filename}: {label} annotation - p1.y >= p4.y (should be <)"
                                )

                            # Check p2.y < p3.y
                            if p2[0] >= p3[0]:
                                errors.append(
                                    f"{filename}: {label} annotation - p2.y >= p3.y (should be <)"
                                )

        return errors
