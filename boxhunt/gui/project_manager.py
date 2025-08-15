"""
Project manager for annotation projects
"""

import json
import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from .logger import logger


class ProjectManager(QObject):
    """Manages annotation projects with SQLite database"""

    # Signals
    project_opened = Signal(str)  # project_path
    project_closed = Signal()
    annotation_saved = Signal(str)  # filename
    annotation_loaded = Signal(str)  # filename

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_path: str | None = None
        self.db_path: str | None = None
        self.connection: sqlite3.Connection | None = None

    def create_project(self, project_path: str) -> bool:
        """Create a new annotation project"""
        try:
            project_dir = Path(project_path)
            if not project_dir.exists():
                project_dir.mkdir(parents=True, exist_ok=True)

            # Check if database already exists
            db_path = project_dir / "annotations.db"
            if db_path.exists():
                reply = QMessageBox.question(
                    None,
                    "Project Exists",
                    f"Project already exists at {project_path}. Do you want to open it instead?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    return self.open_project(project_path)
                else:
                    return False

            # Create database
            self.db_path = str(db_path)
            self.connection = sqlite3.connect(self.db_path)

            # Create annotations table
            cursor = self.connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS annotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    needs_annotation BOOLEAN DEFAULT 1,
                    is_annotated BOOLEAN DEFAULT 0,
                    annotation_result TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster lookups
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filename ON annotations(filename)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_needs_annotation ON annotations(needs_annotation)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_is_annotated ON annotations(is_annotated)"
            )

            self.connection.commit()
            self.current_project_path = project_path

            logger.info(f"Created new project: {project_path}")
            self.project_opened.emit(project_path)
            return True

        except Exception as e:
            logger.error(f"Failed to create project: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to create project: {str(e)}")
            return False

    def open_project(self, project_path: str) -> bool:
        """Open an existing annotation project"""
        try:
            project_dir = Path(project_path)
            if not project_dir.exists():
                QMessageBox.critical(
                    None, "Error", f"Project directory does not exist: {project_path}"
                )
                return False

            db_path = project_dir / "annotations.db"
            if not db_path.exists():
                QMessageBox.critical(
                    None,
                    "Error",
                    f"No annotation database found in project: {project_path}",
                )
                return False

            # Close current project if any
            if self.connection:
                self.connection.close()

            self.db_path = str(db_path)
            self.connection = sqlite3.connect(self.db_path)
            self.current_project_path = project_path

            logger.info(f"Opened project: {project_path}")
            self.project_opened.emit(project_path)
            return True

        except Exception as e:
            logger.error(f"Failed to open project: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to open project: {str(e)}")
            return False

    def close_project(self):
        """Close current project"""
        if self.connection:
            self.connection.close()
            self.connection = None

        self.current_project_path = None
        self.db_path = None

        logger.info("Project closed")
        self.project_closed.emit()

    def is_project_open(self) -> bool:
        """Check if a project is currently open"""
        return self.connection is not None and self.current_project_path is not None

    def get_project_path(self) -> str | None:
        """Get current project path"""
        return self.current_project_path

    def add_image_to_project(
        self, filename: str, needs_annotation: bool = True
    ) -> bool:
        """Add an image to the project database"""
        if not self.is_project_open():
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO annotations (filename, needs_annotation, is_annotated, annotation_result)
                VALUES (?, ?, 0, '{}')
            """,
                (filename, needs_annotation),
            )
            self.connection.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to add image to project: {str(e)}")
            return False

    def get_image_info(self, filename: str) -> dict | None:
        """Get image annotation information"""
        if not self.is_project_open():
            return None

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT filename, needs_annotation, is_annotated, annotation_result
                FROM annotations WHERE filename = ?
            """,
                (filename,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "filename": row[0],
                    "needs_annotation": bool(row[1]),
                    "is_annotated": bool(row[2]),
                    "annotation_result": json.loads(row[3]) if row[3] else {},
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get image info: {str(e)}")
            return None

    def save_annotation(self, filename: str, annotation_data: dict) -> bool:
        """Save annotation data for an image"""
        if not self.is_project_open():
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO annotations
                (filename, needs_annotation, is_annotated, annotation_result, updated_at)
                VALUES (?, 1, 1, ?, CURRENT_TIMESTAMP)
            """,
                (filename, json.dumps(annotation_data)),
            )
            self.connection.commit()

            logger.info(f"Saved annotation for: {filename}")
            self.annotation_saved.emit(filename)
            return True

        except Exception as e:
            logger.error(f"Failed to save annotation: {str(e)}")
            return False

    def load_annotation(self, filename: str) -> dict | None:
        """Load annotation data for an image"""
        if not self.is_project_open():
            return None

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT annotation_result FROM annotations WHERE filename = ?
            """,
                (filename,),
            )

            row = cursor.fetchone()
            if row and row[0]:
                annotation_data = json.loads(row[0])
                logger.info(f"Loaded annotation for: {filename}")
                self.annotation_loaded.emit(filename)
                return annotation_data
            return None

        except Exception as e:
            logger.error(f"Failed to load annotation: {str(e)}")
            return None

    def get_all_annotations(self) -> list[dict]:
        """Get all annotation data for export"""
        if not self.is_project_open():
            return []

        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT filename, annotation_result FROM annotations
                WHERE is_annotated = 1 AND annotation_result != '{}'
            """)

            results = []
            for row in cursor.fetchall():
                if row[1]:  # annotation_result is not empty
                    results.append(
                        {"filename": row[0], "annotation": json.loads(row[1])}
                    )

            return results

        except Exception as e:
            logger.error(f"Failed to get all annotations: {str(e)}")
            return []

    def get_project_statistics(self) -> dict:
        """Get project statistics"""
        if not self.is_project_open():
            return {}

        try:
            cursor = self.connection.cursor()

            # Total images
            cursor.execute("SELECT COUNT(*) FROM annotations")
            total_images = cursor.fetchone()[0]

            # Annotated images (including those with needs_annotation = 0)
            cursor.execute("""
                SELECT COUNT(*) FROM annotations
                WHERE is_annotated = 1 OR needs_annotation = 0
            """)
            annotated_images = cursor.fetchone()[0]

            # Images with actual annotation results
            cursor.execute("""
                SELECT COUNT(*) FROM annotations
                WHERE annotation_result != '{}' AND annotation_result != ''
            """)
            actual_annotated_images = cursor.fetchone()[0]

            # Images needing annotation
            cursor.execute(
                "SELECT COUNT(*) FROM annotations WHERE needs_annotation = 1"
            )
            needs_annotation = cursor.fetchone()[0]

            return {
                "total_images": total_images,
                "annotated_images": annotated_images,
                "actual_annotated_images": actual_annotated_images,
                "needs_annotation": needs_annotation,
                "completion_rate": (annotated_images / total_images * 100)
                if total_images > 0
                else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get project statistics: {str(e)}")
            return {}

    def update_image_list(self, image_files: list[str]) -> bool:
        """Update the project database with current image files"""
        if not self.is_project_open():
            return False

        try:
            cursor = self.connection.cursor()

            # Get existing filenames
            cursor.execute("SELECT filename FROM annotations")
            existing_files = {row[0] for row in cursor.fetchall()}

            # Add new files
            for filename in image_files:
                if filename not in existing_files:
                    cursor.execute(
                        """
                        INSERT INTO annotations (filename, needs_annotation, is_annotated, annotation_result)
                        VALUES (?, 1, 0, '{}')
                    """,
                        (filename,),
                    )

            self.connection.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to update image list: {str(e)}")
            return False

    def set_image_annotation_status(
        self, filename: str, needs_annotation: bool
    ) -> bool:
        """Set whether an image needs annotation"""
        if not self.is_project_open():
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE annotations SET needs_annotation = ? WHERE filename = ?
            """,
                (needs_annotation, filename),
            )

            if cursor.rowcount == 0:
                # Image not in database, add it
                cursor.execute(
                    """
                    INSERT INTO annotations (filename, needs_annotation, is_annotated, annotation_result)
                    VALUES (?, ?, 0, '{}')
                """,
                    (filename, needs_annotation),
                )

            self.connection.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to set image annotation status: {str(e)}")
            return False
