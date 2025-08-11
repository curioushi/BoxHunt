"""
Website scraping client for extracting images from web pages
"""

import asyncio
import logging
import re
from typing import Any, Set
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import aiohttp
from bs4 import BeautifulSoup

from .api_clients import BaseAPIClient, ImageResult
from .config import Config

logger = logging.getLogger(__name__)


class WebsiteClient(BaseAPIClient):
    """Client for scraping images from websites"""

    def __init__(self, base_url: str = "", respect_robots: bool = True, max_depth: int = 1):
        super().__init__()
        self.base_url = base_url
        self.respect_robots = respect_robots
        self.max_depth = max_depth
        self.visited_urls: Set[str] = set()
        self.robots_cache: dict[str, RobotFileParser] = {}

    async def search_images(self, query: str, count: int = 20) -> list[ImageResult]:
        """
        For website client, 'query' is actually the URL to scrape
        This maintains compatibility with the BaseAPIClient interface
        """
        return await self.scrape_website(query, count)

    async def scrape_website(self, url: str, max_images: int = 50) -> list[ImageResult]:
        """Scrape images from a website"""
        logger.info(f"Starting website scrape: {url}")

        # Validate and normalize URL
        if not self._is_valid_url(url):
            logger.error(f"Invalid URL: {url}")
            return []

        self.base_url = self._get_base_url(url)
        self.visited_urls.clear()

        # Check robots.txt if enabled
        if self.respect_robots and not await self._can_fetch(url):
            logger.warning(f"Robots.txt disallows scraping: {url}")
            return []

        results = []
        seen_urls = set()  # Track URLs to avoid duplicates based on URL only
        urls_to_visit = [(url, 0)]  # (url, depth)

        async with aiohttp.ClientSession() as session:
            while urls_to_visit and len(results) < max_images:
                logger.info(f"#URLs: {len(urls_to_visit)}, #Images: {len(results)}")
                current_url, depth = urls_to_visit.pop(0)

                if current_url in self.visited_urls:
                    logger.info(f"Skipping {current_url} because it's already visited")
                    continue
                
                if depth > self.max_depth:
                    logger.info(f"Skipping {current_url} because depth is too high")
                    continue

                self.visited_urls.add(current_url)

                try:
                    # Scrape current page
                    page_results = await self._scrape_page(session, current_url)
                    
                    # Add only new images (based on URL)
                    new_images = []
                    for image_result in page_results:
                        if image_result.url not in seen_urls:
                            seen_urls.add(image_result.url)
                            results.append(image_result)
                            new_images.append(image_result)

                    logger.info(f"Found {len(new_images)}/{len(page_results)} new images on {current_url}")

                    # If we haven't reached max images and depth allows, find more pages
                    if len(results) < max_images and depth < self.max_depth:
                        new_urls = await self._find_page_links(session, current_url, depth + 1)
                        urls_to_visit.extend(new_urls)

                except Exception as e:
                    logger.error(f"Error scraping {current_url}: {e}")

                # Rate limiting
                await asyncio.sleep(Config.REQUEST_DELAY)

        logger.info(f"Website scrape completed: {len(results)} images found from {url}")
        return results

    async def _scrape_page(self, session: aiohttp.ClientSession, url: str) -> list[ImageResult]:
        """Scrape images from a single page"""
        try:
            headers = {"User-Agent": Config.USER_AGENT}
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return []

                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')

                image_urls = set()

                # Extract from img tags
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src:
                        full_url = self._normalize_url(src, url)
                        if full_url and self._is_image_url(full_url):
                            image_urls.add(full_url)

                # Extract from picture tags
                for picture in soup.find_all('picture'):
                    for source in picture.find_all('source'):
                        srcset = source.get('srcset')
                        if srcset:
                            urls = self._extract_from_srcset(srcset, url)
                            image_urls.update(urls)

                # Extract from CSS background images
                css_images = self._extract_css_background_images(html, url)
                image_urls.update(css_images)

                # Convert to ImageResult objects
                results = []
                for img_url in image_urls:
                    # Try to get image dimensions and title
                    img_tag = soup.find('img', src=lambda x: x and img_url.endswith(x.split('/')[-1]))
                    title = ""
                    width = height = 0

                    if img_tag:
                        title = img_tag.get('alt') or img_tag.get('title') or ""
                        try:
                            width = int(img_tag.get('width', 0)) or 0
                            height = int(img_tag.get('height', 0)) or 0
                        except ValueError:
                            pass

                    result = ImageResult(
                        url=img_url,
                        thumbnail_url=img_url,  # Same as original for scraped images
                        title=title,
                        source=self._extract_domain_name(url),
                        width=width,
                        height=height,
                    )
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Error scraping page {url}: {e}")
            return []

    async def _find_page_links(self, session: aiohttp.ClientSession, url: str, depth: int) -> list[tuple[str, int]]:
        """Find additional pages to scrape for images"""
        if depth > self.max_depth:
            return []

        try:
            headers = {"User-Agent": Config.USER_AGENT}
            async with session.get(url, headers=headers, timeout=15) as response:
                if response.status != 200:
                    return []

                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')

                links = set()

                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    full_url = self._normalize_url(href, url)
                    if full_url and full_url not in self.visited_urls:
                        # Check if it's still within the same domain
                        if self._is_same_domain(full_url, self.base_url):
                            links.add((full_url, depth))

                return list(links)

        except Exception as e:
            logger.error(f"Error finding links in {url}: {e}")
            return []

    def _extract_from_srcset(self, srcset: str, base_url: str) -> set[str]:
        """Extract URLs from srcset attribute"""
        urls = set()
        # Parse srcset format: "url 1x, url 2x" or "url 100w, url 200w"
        parts = srcset.split(',')
        for part in parts:
            url_part = part.strip().split()[0]
            full_url = self._normalize_url(url_part, base_url)
            if full_url and self._is_image_url(full_url):
                urls.add(full_url)
        return urls

    def _extract_css_background_images(self, html: str, base_url: str) -> set[str]:
        """Extract background images from CSS"""
        urls = set()
        # Find CSS background-image properties
        pattern = r'background-image:\s*url\(["\']?([^"\')\s]+)["\']?\)'
        matches = re.findall(pattern, html, re.IGNORECASE)
        
        for match in matches:
            full_url = self._normalize_url(match, base_url)
            if full_url and self._is_image_url(full_url):
                urls.add(full_url)
        
        return urls

    def _normalize_url(self, url: str, base_url: str) -> str | None:
        """Convert relative URL to absolute URL"""
        if not url:
            return None
            
        # Remove fragments and clean up
        url = url.split('#')[0].strip()
        if not url:
            return None

        try:
            # Handle data URLs
            if url.startswith('data:'):
                return None
            if url.endswith('.pdf'):
                return None

            # Convert to absolute URL
            full_url = urljoin(base_url, url)
            
            # Validate the URL
            parsed = urlparse(full_url)
            if parsed.scheme not in ('http', 'https'):
                return None
                
            return full_url
        except Exception:
            return None

    def _is_image_url(self, url: str) -> bool:
        """Check if URL points to an image file"""
        if not url:
            return False
            
        # Check file extension
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Common image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}
        
        for ext in image_extensions:
            if ext in path:
                return True
        
        # Some images don't have extensions in URL but have image-related paths
        image_indicators = ['image', 'img', 'photo', 'picture', 'pic']
        return any(indicator in path.lower() for indicator in image_indicators)

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ('http', 'https') and parsed.netloc
        except:
            return False

    def _get_base_url(self, url: str) -> str:
        """Get base URL from full URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _extract_domain_name(self, url: str) -> str:
        """Extract clean domain name from URL for use as source prefix"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix if exists
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Remove port if exists
            domain = domain.split(':')[0]
            
            # Take only the main domain name (remove subdomain and TLD in some cases)
            # For example: deprintedbox.com -> deprintedbox
            parts = domain.split('.')
            if len(parts) >= 2:
                return parts[0]  # Return the main domain part
            else:
                return domain
        except Exception as e:
            logger.warning(f"Error extracting domain name from {url}: {e}")
            return "website"  # Fallback to original name

    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain"""
        try:
            domain1 = urlparse(url1).netloc
            domain2 = urlparse(url2).netloc
            return domain1 == domain2
        except:
            return False

    async def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt"""
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            if base_url not in self.robots_cache:
                robots_url = urljoin(base_url, '/robots.txt')
                rp = RobotFileParser()
                rp.set_url(robots_url)
                
                try:
                    # Simple synchronous read for robots.txt
                    import requests
                    resp = requests.get(robots_url, timeout=5)
                    if resp.status_code == 200:
                        rp.set_content(resp.text.encode())
                    rp.read()
                except:
                    # If robots.txt can't be read, assume it's OK to scrape
                    pass
                    
                self.robots_cache[base_url] = rp

            rp = self.robots_cache[base_url]
            return rp.can_fetch(Config.USER_AGENT, url)
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt: {e}")
            return True  # Allow if can't check 