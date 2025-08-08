"""
Configuration module for BoxHunt image scraper
"""
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration settings for the image scraper"""
    
    # API Keys (set these in your .env file)
    UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY', '')
    PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
    
    # Search Keywords
    KEYWORDS_EN = [
        "cardboard box",
        "corrugated box", 
        "carton",
        "shipping box",
        "moving box",
        "packaging box",
        "brown cardboard box",
        "empty cardboard box"
    ]
    
    KEYWORDS_CN = [
        "纸箱",
        "瓦楞纸箱", 
        "搬家箱",
        "快递箱",
        "包装箱",
        "纸盒",
        "牛皮纸箱"
    ]
    
    # Image filtering settings
    MIN_IMAGE_WIDTH = 256
    MIN_IMAGE_HEIGHT = 256
    ALLOWED_FORMATS = ['jpg', 'jpeg', 'png', 'webp']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Rate limiting
    REQUEST_DELAY = 1.0  # seconds between requests
    MAX_CONCURRENT_REQUESTS = 3
    
    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    # Storage settings
    DATA_DIR = "data"
    IMAGES_DIR = os.path.join(DATA_DIR, "images")
    CACHE_DIR = os.path.join(DATA_DIR, "cache")
    METADATA_FILE = os.path.join(DATA_DIR, "metadata.csv")
    
    # API endpoints
    UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
    PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
    
    # User agent for web requests
    USER_AGENT = "BoxHunt/1.0 (Image Scraper for Research Purposes)"
    
    @classmethod
    def get_all_keywords(cls) -> List[str]:
        """Get all keywords (English + Chinese)"""
        return cls.KEYWORDS_EN + cls.KEYWORDS_CN
    
    @classmethod
    def validate_api_keys(cls) -> Dict[str, bool]:
        """Check which API keys are available"""
        return {
            'unsplash': bool(cls.UNSPLASH_ACCESS_KEY),
            'pexels': bool(cls.PEXELS_API_KEY)
        }