"""
Image processing module for downloading, deduplication, and quality control
"""
import os
import hashlib
import asyncio
import aiohttp
import logging
from io import BytesIO
from PIL import Image
import imagehash
from typing import Optional, Tuple, Set
from urllib.parse import urlparse
import time

from .config import Config
from .api_clients import ImageResult

logger = logging.getLogger(__name__)

class ImageProcessor:
    """Handles image downloading, processing, and deduplication"""
    
    def __init__(self):
        self.downloaded_hashes: Set[str] = set()
        self.failed_urls: Set[str] = set()
        
        # Ensure directories exist
        os.makedirs(Config.IMAGES_DIR, exist_ok=True)
        os.makedirs(Config.CACHE_DIR, exist_ok=True)
    
    def _generate_filename(self, url: str, source: str) -> str:
        """Generate a unique filename for the image"""
        # Get file extension from URL
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        # Try to extract extension from URL
        for ext in Config.ALLOWED_FORMATS:
            if f'.{ext}' in path:
                extension = ext
                break
        else:
            extension = 'jpg'  # Default extension
        
        # Create filename from URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        timestamp = int(time.time())
        
        return f"{source}_{timestamp}_{url_hash}.{extension}"
    
    async def _download_image(self, session: aiohttp.ClientSession, 
                            url: str) -> Optional[bytes]:
        """Download image from URL"""
        if url in self.failed_urls:
            return None
            
        try:
            headers = {'User-Agent': Config.USER_AGENT}
            
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content_length = response.headers.get('content-length')
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
    
    def _validate_image(self, image_data: bytes) -> Optional[Tuple[Image.Image, str]]:
        """Validate and process image data"""
        try:
            # Try to open and validate the image
            image = Image.open(BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Check dimensions
            width, height = image.size
            if width < Config.MIN_IMAGE_WIDTH or height < Config.MIN_IMAGE_HEIGHT:
                logger.debug(f"Image too small: {width}x{height}")
                return None
            
            # Check format
            format_lower = image.format.lower() if image.format else 'jpeg'
            if format_lower not in ['jpeg', 'jpg', 'png', 'webp']:
                format_lower = 'jpeg'  # Default to JPEG
            
            return image, format_lower
            
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
    
    async def process_image(self, session: aiohttp.ClientSession, 
                          image_result: ImageResult) -> Optional[dict]:
        """Process a single image: download, validate, deduplicate, and save"""
        
        # Download image
        image_data = await self._download_image(session, image_result.url)
        if not image_data:
            return None
        
        # Validate image
        validation_result = self._validate_image(image_data)
        if not validation_result:
            return None
            
        image, format_name = validation_result
        
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
        filepath = os.path.join(Config.IMAGES_DIR, filename)
        
        try:
            # Save image
            if format_name == 'jpeg':
                image.save(filepath, 'JPEG', quality=85, optimize=True)
            else:
                image.save(filepath, format_name.upper())
            
            # Add hash to set
            self.downloaded_hashes.add(phash)
            
            # Return metadata
            width, height = image.size
            file_size = os.path.getsize(filepath)
            
            return {
                'filename': filename,
                'filepath': filepath,
                'url': image_result.url,
                'source': image_result.source,
                'title': image_result.title,
                'width': width,
                'height': height,
                'file_size': file_size,
                'perceptual_hash': phash,
                'download_time': time.time()
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
        
        logger.info(f"Successfully processed {len(successful_results)} out of {len(image_results)} images")
        return successful_results
    
    def load_existing_hashes(self, metadata_file: str) -> None:
        """Load existing perceptual hashes from metadata to avoid re-downloading"""
        try:
            import pandas as pd
            if os.path.exists(metadata_file):
                df = pd.read_csv(metadata_file)
                if 'perceptual_hash' in df.columns:
                    self.downloaded_hashes.update(
                        df['perceptual_hash'].dropna().astype(str).tolist()
                    )
                    logger.info(f"Loaded {len(self.downloaded_hashes)} existing hashes")
        except Exception as e:
            logger.error(f"Error loading existing hashes: {e}")