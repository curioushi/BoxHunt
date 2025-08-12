"""
Storage management for images and metadata
"""

import csv
import logging
import os
from datetime import datetime
from typing import Any

import pandas as pd

from .config import Config

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages storage of images and metadata"""

    def __init__(self, domain_name: str = None, metadata_file: str = None):
        self.domain_name = domain_name
        if domain_name:
            self.images_dir = Config.get_domain_images_dir(domain_name)
            self.metadata_file = metadata_file or Config.get_domain_metadata_file(domain_name)
        else:
            # Legacy support: if no domain specified, use old behavior
            self.images_dir = os.path.join(Config.DATA_DIR, "images") 
            self.metadata_file = metadata_file or os.path.join(Config.DATA_DIR, "metadata.csv")
        
        self.ensure_directories()
        self.init_metadata_file()

    def ensure_directories(self):
        """Create necessary directories"""
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        # Directory for metadata file
        os.makedirs(os.path.dirname(self.metadata_file), exist_ok=True)

    def init_metadata_file(self):
        """Initialize metadata CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.metadata_file):
            headers = [
                "id",
                "filename",
                "url",
                "source",
                "title",
                "width",
                "height",
                "file_size",
                "perceptual_hash",
                "download_time",
                "created_at",
                "status",
            ]

            with open(self.metadata_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)

            logger.info(f"Created metadata file: {self.metadata_file}")

    def save_image_metadata(self, metadata_list: list[dict[str, Any]]) -> bool:
        """Save image metadata to CSV file"""
        if not metadata_list:
            return True

        try:
            # Load existing data to get next ID
            next_id = self._get_next_id()

            # Prepare records with IDs and timestamps
            current_time = datetime.now().isoformat()
            records = []

            for i, metadata in enumerate(metadata_list):
                record = {
                    "id": next_id + i,
                    "filename": metadata.get("filename", ""),
                    "url": metadata.get("url", ""),
                    "source": metadata.get("source", ""),
                    "title": metadata.get("title", ""),
                    "width": metadata.get("width", 0),
                    "height": metadata.get("height", 0),
                    "file_size": metadata.get("file_size", 0),
                    "perceptual_hash": metadata.get("perceptual_hash", ""),
                    "download_time": metadata.get("download_time", ""),
                    "created_at": current_time,
                    "status": "downloaded",
                }
                records.append(record)

            # Append to CSV file
            df_new = pd.DataFrame(records)

            if os.path.exists(self.metadata_file):
                # Append to existing file
                df_new.to_csv(
                    self.metadata_file,
                    mode="a",
                    header=False,
                    index=False,
                    encoding="utf-8",
                )
            else:
                # Create new file
                df_new.to_csv(self.metadata_file, index=False, encoding="utf-8")

            logger.info(f"Saved metadata for {len(records)} images")
            return True

        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            return False

    def _get_next_id(self) -> int:
        """Get the next available ID"""
        try:
            if os.path.exists(self.metadata_file):
                df = pd.read_csv(self.metadata_file)
                if len(df) > 0 and "id" in df.columns:
                    return df["id"].max() + 1
            return 1
        except Exception as e:
            logger.error(f"Error getting next ID: {e}")
            return 1

    def get_existing_urls(self) -> set:
        """Get set of already downloaded URLs"""
        try:
            if os.path.exists(self.metadata_file):
                df = pd.read_csv(self.metadata_file)
                if "url" in df.columns:
                    return set(df["url"].dropna().tolist())
            return set()
        except Exception as e:
            logger.error(f"Error loading existing URLs: {e}")
            return set()

    def get_existing_hashes(self) -> set:
        """Get set of existing perceptual hashes"""
        try:
            if os.path.exists(self.metadata_file):
                df = pd.read_csv(self.metadata_file)
                if "perceptual_hash" in df.columns:
                    return set(df["perceptual_hash"].dropna().astype(str).tolist())
            return set()
        except Exception as e:
            logger.error(f"Error loading existing hashes: {e}")
            return set()

    def get_statistics(self) -> dict[str, Any]:
        """Get storage statistics"""
        try:
            stats = {
                "total_images": 0,
                "total_size": 0,
                "sources": {},
                "avg_width": 0,
                "avg_height": 0,
                "file_formats": {},
            }

            if not os.path.exists(self.metadata_file):
                return stats

            df = pd.read_csv(self.metadata_file)

            if len(df) == 0:
                return stats

            stats["total_images"] = len(df)
            stats["total_size"] = (
                df["file_size"].sum() if "file_size" in df.columns else 0
            )

            # Source statistics
            if "source" in df.columns:
                stats["sources"] = df["source"].value_counts().to_dict()

            # Average dimensions
            if "width" in df.columns and "height" in df.columns:
                stats["avg_width"] = int(df["width"].mean())
                stats["avg_height"] = int(df["height"].mean())

            # File format statistics (from filenames)
            if "filename" in df.columns:
                formats = {}
                for filename in df["filename"].dropna():
                    ext = os.path.splitext(filename)[1].lower().lstrip(".")
                    formats[ext] = formats.get(ext, 0) + 1
                stats["file_formats"] = formats

            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "total_images": 0,
                "total_size": 0,
                "sources": {},
                "avg_width": 0,
                "avg_height": 0,
                "file_formats": {},
            }

    def cleanup_orphaned_files(self) -> int:
        """Remove image files that don't have metadata entries"""
        try:
            if not os.path.exists(self.metadata_file):
                return 0

            # Get list of files in metadata
            df = pd.read_csv(self.metadata_file)
            if "filename" not in df.columns:
                return 0

            metadata_files = set(df["filename"].dropna().tolist())

            # Get list of actual image files
            image_files = set()
            if os.path.exists(self.images_dir):
                for filename in os.listdir(self.images_dir):
                    if any(
                        filename.lower().endswith(f".{ext}")
                        for ext in Config.ALLOWED_FORMATS
                    ):
                        image_files.add(filename)

            # Find orphaned files
            orphaned_files = image_files - metadata_files

            # Remove orphaned files
            removed_count = 0
            for filename in orphaned_files:
                try:
                    filepath = os.path.join(self.images_dir, filename)
                    os.remove(filepath)
                    removed_count += 1
                    logger.debug(f"Removed orphaned file: {filename}")
                except Exception as e:
                    logger.error(f"Error removing {filename}: {e}")

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} orphaned files")

            return removed_count

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def export_metadata(
        self, output_file: str = None, format: str = "csv"
    ) -> str | None:
        """Export metadata to different formats"""
        try:
            if not os.path.exists(self.metadata_file):
                logger.warning("No metadata file found")
                return None

            df = pd.read_csv(self.metadata_file)

            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(
                    Config.DATA_DIR, f"metadata_export_{timestamp}.{format}"
                )

            if format.lower() == "json":
                df.to_json(output_file, orient="records", indent=2)
            elif format.lower() == "xlsx":
                df.to_excel(output_file, index=False)
            else:  # default to CSV
                df.to_csv(output_file, index=False, encoding="utf-8")

            logger.info(f"Metadata exported to: {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Error exporting metadata: {e}")
            return None
