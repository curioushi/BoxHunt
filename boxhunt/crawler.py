"""
Main crawler class that coordinates all components
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from tqdm.asyncio import tqdm

from .config import Config
from .api_clients import APIManager, ImageResult
from .image_processor import ImageProcessor
from .storage import StorageManager

logger = logging.getLogger(__name__)

class BoxHuntCrawler:
    """Main crawler class for collecting cardboard box images"""
    
    def __init__(self, metadata_file: str = None, enabled_sources: List[str] = None):
        self.api_manager = APIManager(enabled_sources)
        self.image_processor = ImageProcessor()
        self.storage_manager = StorageManager(metadata_file)
        
        # Load existing hashes for deduplication
        self.image_processor.load_existing_hashes(self.storage_manager.metadata_file)
        
        logger.info("BoxHunt crawler initialized")
        self._log_status()
    
    def _log_status(self):
        """Log current status and available sources"""
        sources = self.api_manager.get_available_sources()
        if sources:
            logger.info(f"Available API sources: {', '.join(sources)}")
        else:
            logger.warning("No API sources available. Please check your API keys.")
        
        stats = self.storage_manager.get_statistics()
        if stats['total_images'] > 0:
            logger.info(f"Existing collection: {stats['total_images']} images")
    
    async def crawl_single_keyword(self, keyword: str, 
                                 max_images_per_source: int = 20,
                                 process_images: bool = True) -> Dict[str, Any]:
        """Crawl images for a single keyword"""
        logger.info(f"Starting crawl for keyword: '{keyword}'")
        
        # Search all sources
        search_results = await self.api_manager.search_all_sources(
            keyword, max_images_per_source
        )
        
        if not search_results:
            logger.warning(f"No search results found for keyword: {keyword}")
            return {
                'keyword': keyword,
                'found_images': 0,
                'processed_images': 0,
                'saved_images': 0,
                'results': []
            }
        
        logger.info(f"Found {len(search_results)} images for keyword: {keyword}")
        
        if not process_images:
            return {
                'keyword': keyword,
                'found_images': len(search_results),
                'processed_images': 0,
                'saved_images': 0,
                'results': [img.to_dict() for img in search_results]
            }
        
        # Process images (download, validate, deduplicate)
        processed_results = await self._process_with_progress(
            search_results, f"Processing images for '{keyword}'"
        )
        
        # Save metadata
        saved_count = 0
        if processed_results:
            if self.storage_manager.save_image_metadata(processed_results):
                saved_count = len(processed_results)
        
        logger.info(f"Keyword '{keyword}' completed: {saved_count} images saved")
        
        return {
            'keyword': keyword,
            'found_images': len(search_results),
            'processed_images': len(processed_results),
            'saved_images': saved_count,
            'results': processed_results
        }
    
    async def crawl_multiple_keywords(self, keywords: List[str] = None,
                                    max_images_per_source: int = 20,
                                    delay_between_keywords: float = None) -> Dict[str, Any]:
        """Crawl images for multiple keywords"""
        if keywords is None:
            keywords = Config.get_all_keywords()
        
        if delay_between_keywords is None:
            delay_between_keywords = Config.REQUEST_DELAY
        
        logger.info(f"Starting multi-keyword crawl for {len(keywords)} keywords")
        
        results = {
            'total_keywords': len(keywords),
            'completed_keywords': 0,
            'total_found_images': 0,
            'total_processed_images': 0,
            'total_saved_images': 0,
            'keyword_results': [],
            'errors': []
        }
        
        for i, keyword in enumerate(keywords):
            try:
                result = await self.crawl_single_keyword(
                    keyword, max_images_per_source
                )
                
                results['keyword_results'].append(result)
                results['completed_keywords'] += 1
                results['total_found_images'] += result['found_images']
                results['total_processed_images'] += result['processed_images']
                results['total_saved_images'] += result['saved_images']
                
                # Progress update
                logger.info(
                    f"Progress: {i+1}/{len(keywords)} keywords completed. "
                    f"Total saved: {results['total_saved_images']} images"
                )
                
                # Delay between keywords to be respectful
                if i < len(keywords) - 1 and delay_between_keywords > 0:
                    await asyncio.sleep(delay_between_keywords)
                    
            except Exception as e:
                error_msg = f"Error processing keyword '{keyword}': {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)
        
        logger.info(
            f"Multi-keyword crawl completed: {results['total_saved_images']} "
            f"images saved from {results['completed_keywords']} keywords"
        )
        
        return results
    
    async def _process_with_progress(self, search_results: List[ImageResult], 
                                   description: str) -> List[Dict[str, Any]]:
        """Process images with progress bar"""
        if not search_results:
            return []
        
        # Create progress bar
        pbar = tqdm(
            total=len(search_results),
            desc=description,
            unit="img"
        )
        
        # Process in batches to show progress
        batch_size = max(1, min(Config.MAX_CONCURRENT_REQUESTS, len(search_results) // 10))
        all_results = []
        
        for i in range(0, len(search_results), batch_size):
            batch = search_results[i:i + batch_size]
            batch_results = await self.image_processor.process_image_batch(batch)
            all_results.extend(batch_results)
            
            pbar.update(len(batch))
        
        pbar.close()
        return all_results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        storage_stats = self.storage_manager.get_statistics()
        
        stats = {
            'storage': storage_stats,
            'api_sources': self.api_manager.get_available_sources(),
            'failed_urls_count': len(self.image_processor.failed_urls),
            'unique_hashes_count': len(self.image_processor.downloaded_hashes)
        }
        
        return stats
    
    def cleanup(self) -> Dict[str, int]:
        """Perform cleanup operations"""
        logger.info("Starting cleanup operations...")
        
        orphaned_files = self.storage_manager.cleanup_orphaned_files()
        
        # Clear failed URLs (they might work now)
        failed_urls_cleared = len(self.image_processor.failed_urls)
        self.image_processor.failed_urls.clear()
        
        cleanup_stats = {
            'orphaned_files_removed': orphaned_files,
            'failed_urls_cleared': failed_urls_cleared
        }
        
        logger.info(f"Cleanup completed: {cleanup_stats}")
        return cleanup_stats
    
    async def resume_crawl(self, keywords: List[str] = None,
                         max_images_per_source: int = 20) -> Dict[str, Any]:
        """Resume crawling by avoiding already downloaded images"""
        logger.info("Resuming crawl (skipping existing images)...")
        
        # Reload existing hashes
        self.image_processor.downloaded_hashes = self.storage_manager.get_existing_hashes()
        
        # Continue with regular crawl
        return await self.crawl_multiple_keywords(keywords, max_images_per_source)
    
    def export_results(self, format: str = 'csv') -> Optional[str]:
        """Export crawl results"""
        return self.storage_manager.export_metadata(format=format)
    
    async def test_apis(self) -> Dict[str, Any]:
        """Test all available APIs with a simple query"""
        test_query = "cardboard box"
        logger.info(f"Testing APIs with query: '{test_query}'")
        
        results = {}
        
        for source in self.api_manager.get_available_sources():
            try:
                client = self.api_manager.clients[source]
                search_results = await client.search_images(test_query, count=5)
                
                results[source] = {
                    'status': 'success',
                    'results_count': len(search_results),
                    'sample_urls': [img.url for img in search_results[:3]]
                }
                
                logger.info(f"{source}: {len(search_results)} results")
                
            except Exception as e:
                results[source] = {
                    'status': 'error',
                    'error': str(e)
                }
                logger.error(f"{source}: {str(e)}")
        
        return results