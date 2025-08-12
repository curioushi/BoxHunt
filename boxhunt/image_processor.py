"""
Image processing module for downloading, deduplication, and quality control
"""

import asyncio
import hashlib
import logging
import os
import time
from io import BytesIO

import aiohttp
import imagehash
from PIL import Image

from .api_clients import ImageResult
from .config import Config

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image downloading, processing, and deduplication"""

    def __init__(self, domain_name: str = None):
        self.downloaded_hashes: set[str] = set()
        self.failed_urls: set[str] = set()
        self.domain_name = domain_name

        if domain_name:
            self.images_dir = Config.get_domain_images_dir(domain_name)
        else:
            # Legacy support: if no domain specified, use old behavior
            self.images_dir = os.path.join(Config.DATA_DIR, "images")

        # Ensure directories exist
        os.makedirs(self.images_dir, exist_ok=True)

    def _generate_filename(self, url: str, source: str) -> str:
        """Generate a unique filename for the image"""
        # Create filename from URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        timestamp = int(time.time())

        return f"{source}_{timestamp}_{url_hash}.jpg"

    async def _download_image(
        self, session: aiohttp.ClientSession, url: str
    ) -> bytes | None:
        """Download image from URL"""
        if url in self.failed_urls:
            return None

        try:
            headers = {"User-Agent": Config.USER_AGENT}

            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > Config.MAX_FILE_SIZE:
                        logger.warning(f"Image too large: {url}")
                        self.failed_urls.add(url)
                        return None

                    image_data = await response.read()

                    if len(image_data) > Config.MAX_FILE_SIZE:
                        logger.warning(f"Image too large after download: {url}")
                        self.failed_urls.add(url)
                        return None

                    return image_data
                else:
                    logger.warning(f"Failed to download {url}: HTTP {response.status}")
                    self.failed_urls.add(url)
                    return None

        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            self.failed_urls.add(url)
            return None

    def _validate_image(self, image_data: bytes) -> tuple[Image.Image, str] | None:
        """Validate and process image data"""
        try:
            # Try to open and validate the image
            image = Image.open(BytesIO(image_data))

            # Convert to RGB if necessary
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # Check dimensions
            width, height = image.size
            if width < Config.MIN_IMAGE_WIDTH or height < Config.MIN_IMAGE_HEIGHT:
                logger.debug(f"Image too small: {width}x{height}")
                return None

            return image

        except Exception as e:
            logger.error(f"Invalid image data: {e}")
            return None

    def _calculate_perceptual_hash(self, image: Image.Image) -> str:
        """Calculate perceptual hash for deduplication"""
        try:
            # Use average hash for better performance
            phash = imagehash.average_hash(image)
            return str(phash)
        except Exception as e:
            logger.error(f"Error calculating hash: {e}")
            return ""

    def _is_duplicate(self, phash: str, threshold: int = 5) -> bool:
        """Check if image is a duplicate based on perceptual hash"""
        if not phash:
            return False

        try:
            current_hash = imagehash.hex_to_hash(phash)

            for existing_hash_str in self.downloaded_hashes:
                existing_hash = imagehash.hex_to_hash(existing_hash_str)

                # Calculate Hamming distance
                distance = current_hash - existing_hash
                if distance <= threshold:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking duplicate: {e}")
            return False

    async def process_image(
        self, session: aiohttp.ClientSession, image_result: ImageResult
    ) -> dict | None:
        """Process a single image: download, validate, deduplicate, and save"""

        # Download image
        image_data = await self._download_image(session, image_result.url)
        if not image_data:
            return None

        # Validate image
        image = self._validate_image(image_data)
        if not image:
            return None

        # Calculate perceptual hash
        phash = self._calculate_perceptual_hash(image)
        if not phash:
            return None

        # Check for duplicates
        if self._is_duplicate(phash):
            logger.debug(f"Duplicate image skipped: {image_result.url}")
            return None

        # Generate filename and save
        filename = self._generate_filename(image_result.url, image_result.source)
        filepath = os.path.join(self.images_dir, filename)

        try:
            # Save image
            image.save(filepath, "JPEG", quality=95, optimize=True)

            # Add hash to set
            self.downloaded_hashes.add(phash)

            # Return metadata
            width, height = image.size
            file_size = os.path.getsize(filepath)

            return {
                "filename": filename,
                "filepath": filepath,
                "url": image_result.url,
                "source": image_result.source,
                "title": image_result.title,
                "width": width,
                "height": height,
                "file_size": file_size,
                "perceptual_hash": phash,
                "download_time": time.time(),
            }

        except Exception as e:
            logger.error(f"Error saving image {filename}: {e}")
            return None

    async def process_image_batch(self, image_results: list) -> list:
        """Process a batch of images concurrently"""
        if not image_results:
            return []

        # Create semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS)

        async def process_with_semaphore(session, image_result):
            async with semaphore:
                return await self.process_image(session, image_result)

        # Process all images
        async with aiohttp.ClientSession() as session:
            tasks = [
                process_with_semaphore(session, img_result)
                for img_result in image_results
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None results and exceptions
        successful_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Image processing failed: {result}")
            elif result is not None:
                successful_results.append(result)

        logger.info(
            f"Successfully processed {len(successful_results)} out of {len(image_results)} images"
        )
        return successful_results
