"""
Configuration module for BoxHunt image scraper
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration settings for the image scraper"""

    # API endpoints
    PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

    # API Keys (set these in your .env file)
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

    # Search Keywords
    KEYWORDS_EN = [
        "cardboard box",
        "corrugated box",
        "carton",
        "shipping box",
        "moving box",
        "packaging box",
        "brown cardboard box",
        "empty cardboard box",
    ]

    KEYWORDS_CN = ["纸箱", "瓦楞纸箱", "搬家箱", "快递箱", "包装箱", "纸盒", "牛皮纸箱"]

    # Website scraping settings
    MAX_SCRAPING_DEPTH = 2  # Maximum depth for recursive scraping
    RESPECT_ROBOTS_TXT = False  # Whether to respect robots.txt
    MAX_IMAGES_PER_WEBSITE = 100  # Maximum images per website

    # Image filtering settings
    MIN_IMAGE_WIDTH = 256
    MIN_IMAGE_HEIGHT = 256
    ALLOWED_FORMATS = ["jpg", "jpeg", "png", "webp"]
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    # Rate limiting
    REQUEST_DELAY = 0.2  # seconds between requests
    MAX_CONCURRENT_REQUESTS = 3

    # Storage settings
    DATA_DIR = "data"

    # User agent for web requests
    USER_AGENT = "BoxHunt/1.0 (Image Scraper for Research Purposes)"

    @classmethod
    def get_all_keywords(cls) -> list[str]:
        """Get all keywords (English + Chinese)"""
        return cls.KEYWORDS_EN + cls.KEYWORDS_CN

    @classmethod
    def get_domain_images_dir(cls, domain_name: str) -> str:
        """Get images directory for a specific domain"""
        return os.path.join(cls.DATA_DIR, domain_name, "images")
    
    @classmethod
    def get_domain_metadata_file(cls, domain_name: str) -> str:
        """Get metadata file path for a specific domain"""
        return os.path.join(cls.DATA_DIR, domain_name, "metadata.csv")

    @classmethod
    def validate_api_keys(cls) -> dict[str, bool]:
        """Check which API keys are available"""
        return {
            "pexels": bool(cls.PEXELS_API_KEY),
            "website": True,  # Website scraping doesn't need API key
        }
