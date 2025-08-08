"""
API clients for different image sources
"""
import asyncio
import aiohttp
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

from .config import Config

logger = logging.getLogger(__name__)

class ImageResult:
    """Represents an image search result"""
    def __init__(self, url: str, thumbnail_url: str = "", title: str = "", 
                 source: str = "", width: int = 0, height: int = 0):
        self.url = url
        self.thumbnail_url = thumbnail_url
        self.title = title
        self.source = source
        self.width = width
        self.height = height
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'url': self.url,
            'thumbnail_url': self.thumbnail_url, 
            'title': self.title,
            'source': self.source,
            'width': self.width,
            'height': self.height
        }

class BaseAPIClient(ABC):
    """Base class for API clients"""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        
    @abstractmethod
    async def search_images(self, query: str, count: int = 20) -> List[ImageResult]:
        """Search for images using the API"""
        pass
    
    async def _make_request(self, session: aiohttp.ClientSession, 
                          url: str, params: Dict[str, Any] = None,
                          headers: Dict[str, str] = None) -> Optional[Dict[str, Any]]:
        """Make an async HTTP request"""
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API request failed with status {response.status}: {await response.text()}")
                    return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None

class BingAPIClient(BaseAPIClient):
    """Bing Image Search API client"""
    
    async def search_images(self, query: str, count: int = 20) -> List[ImageResult]:
        """Search images using Bing API"""
        if not self.api_key:
            logger.warning("Bing API key not provided")
            return []
            
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'User-Agent': Config.USER_AGENT
        }
        
        params = {
            'q': query,
            'count': min(count, 150),  # Bing API limit
            'imageType': 'photo',
            'size': 'medium',
            'aspect': 'all',
            'freshness': 'all',
            'safeSearch': 'moderate'
        }
        
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, Config.BING_SEARCH_URL, params, headers)
            
            if not data or 'value' not in data:
                return []
                
            results = []
            for item in data['value']:
                result = ImageResult(
                    url=item.get('contentUrl', ''),
                    thumbnail_url=item.get('thumbnailUrl', ''),
                    title=item.get('name', ''),
                    source='bing',
                    width=item.get('width', 0),
                    height=item.get('height', 0)
                )
                results.append(result)
                
            return results

class UnsplashAPIClient(BaseAPIClient):
    """Unsplash API client"""
    
    async def search_images(self, query: str, count: int = 20) -> List[ImageResult]:
        """Search images using Unsplash API"""
        if not self.api_key:
            logger.warning("Unsplash API key not provided") 
            return []
            
        headers = {
            'Authorization': f'Client-ID {self.api_key}',
            'User-Agent': Config.USER_AGENT
        }
        
        params = {
            'query': query,
            'per_page': min(count, 30),  # Unsplash API limit
            'orientation': 'all'
        }
        
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, Config.UNSPLASH_SEARCH_URL, params, headers)
            
            if not data or 'results' not in data:
                return []
                
            results = []
            for item in data['results']:
                result = ImageResult(
                    url=item['urls']['regular'],
                    thumbnail_url=item['urls']['thumb'],
                    title=item.get('description', item.get('alt_description', '')),
                    source='unsplash',
                    width=item.get('width', 0),
                    height=item.get('height', 0)
                )
                results.append(result)
                
            return results

class PexelsAPIClient(BaseAPIClient):
    """Pexels API client"""
    
    async def search_images(self, query: str, count: int = 20) -> List[ImageResult]:
        """Search images using Pexels API"""
        if not self.api_key:
            logger.warning("Pexels API key not provided")
            return []
            
        headers = {
            'Authorization': self.api_key,
            'User-Agent': Config.USER_AGENT
        }
        
        params = {
            'query': query,
            'per_page': min(count, 80),  # Pexels API limit
            'size': 'medium'
        }
        
        async with aiohttp.ClientSession() as session:
            data = await self._make_request(session, Config.PEXELS_SEARCH_URL, params, headers)
            
            if not data or 'photos' not in data:
                return []
                
            results = []
            for item in data['photos']:
                result = ImageResult(
                    url=item['src']['original'],
                    thumbnail_url=item['src']['medium'],
                    title=item.get('alt', ''),
                    source='pexels',
                    width=item.get('width', 0),
                    height=item.get('height', 0)
                )
                results.append(result)
                
            return results

class APIManager:
    """Manages multiple API clients"""
    
    def __init__(self):
        self.clients = {}
        
        # Initialize available clients
        api_keys = Config.validate_api_keys()
        
        if api_keys['bing']:
            self.clients['bing'] = BingAPIClient(Config.BING_API_KEY)
            logger.info("Bing API client initialized")
            
        if api_keys['unsplash']:
            self.clients['unsplash'] = UnsplashAPIClient(Config.UNSPLASH_ACCESS_KEY)
            logger.info("Unsplash API client initialized")
            
        if api_keys['pexels']:
            self.clients['pexels'] = PexelsAPIClient(Config.PEXELS_API_KEY)
            logger.info("Pexels API client initialized")
            
        if not self.clients:
            logger.warning("No API clients initialized. Please check your API keys in .env file")
    
    async def search_all_sources(self, query: str, count_per_source: int = 20) -> List[ImageResult]:
        """Search all available sources concurrently"""
        if not self.clients:
            logger.error("No API clients available")
            return []
            
        tasks = []
        for name, client in self.clients.items():
            task = asyncio.create_task(client.search_images(query, count_per_source))
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_images = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Search failed for {list(self.clients.keys())[i]}: {result}")
            else:
                all_images.extend(result)
                
        logger.info(f"Found {len(all_images)} images total for query: {query}")
        return all_images
    
    def get_available_sources(self) -> List[str]:
        """Get list of available API sources"""
        return list(self.clients.keys())