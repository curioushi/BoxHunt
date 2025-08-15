"""
Main entry point for BoxHunt image scraper
"""

import argparse
import asyncio
import logging
import sys

from .config import Config
from .crawler import BoxHuntCrawler


def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("boxhunt.log"),
        ],
    )


def print_banner():
    """Print application banner"""
    banner = """
    ╔══════════════════════════════════════╗
    ║              BoxHunt                 ║
    ║        Cardboard Box Image           ║
    ║           Web Scraper                ║
    ╚══════════════════════════════════════╝
    """
    print(banner)


async def cmd_crawl(args):
    """Handle crawl command"""
    # Parse enabled sources if provided
    enabled_sources = None
    if args.sources:
        enabled_sources = [s.strip() for s in args.sources.split(",")]

    crawler = BoxHuntCrawler(enabled_sources=enabled_sources)

    # Use custom keywords if provided
    keywords = None
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",")]

    # Start crawling
    if keywords and len(keywords) == 1:
        result = await crawler.crawl_single_keyword(
            keywords[0], max_images_per_source=args.max_images
        )
        print(f"\n✓ Crawl completed for '{keywords[0]}':")
        print(f"  Found: {result['found_images']} images")
        print(f"  Saved: {result['saved_images']} images")
    else:
        result = await crawler.crawl_multiple_keywords(
            keywords=keywords,
            max_images_per_source=args.max_images,
            delay_between_keywords=args.delay,
        )
        print("\n✓ Multi-keyword crawl completed:")
        print(
            f"  Keywords processed: {result['completed_keywords']}/{result['total_keywords']}"
        )
        print(f"  Total images found: {result['total_found_images']}")
        print(f"  Total images saved: {result['total_saved_images']}")

        if result["errors"]:
            print(f"  Errors: {len(result['errors'])}")
            for error in result["errors"]:
                print(f"    - {error}")


async def cmd_resume(args):
    """Handle resume command"""
    # Parse enabled sources if provided
    enabled_sources = None
    if args.sources:
        enabled_sources = [s.strip() for s in args.sources.split(",")]

    crawler = BoxHuntCrawler(enabled_sources=enabled_sources)

    keywords = None
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",")]

    result = await crawler.resume_crawl(
        keywords=keywords, max_images_per_source=args.max_images
    )

    print("\n✓ Resume crawl completed:")
    print(
        f"  Keywords processed: {result['completed_keywords']}/{result['total_keywords']}"
    )
    print(f"  Total images saved: {result['total_saved_images']}")


async def cmd_test(args):
    """Handle test command"""
    crawler = BoxHuntCrawler()

    print("Testing API connections...")
    results = await crawler.test_apis()

    print("\n🧪 API Test Results:")
    for source, result in results.items():
        if result["status"] == "success":
            print(f"  ✓ {source}: {result['results_count']} results")
        else:
            print(f"  ✗ {source}: {result['error']}")


def cmd_stats(args):
    """Handle stats command"""
    crawler = BoxHuntCrawler()
    stats = crawler.get_statistics()

    print("\n📊 BoxHunt Statistics:")
    print(f"  Total images: {stats['storage']['total_images']}")
    print(f"  Total size: {stats['storage']['total_size'] / (1024 * 1024):.2f} MB")
    print(
        f"  Average dimensions: {stats['storage']['avg_width']}×{stats['storage']['avg_height']}"
    )

    if stats["storage"]["sources"]:
        print("  Sources:")
        for source, count in stats["storage"]["sources"].items():
            print(f"    - {source}: {count} images")

    if stats["storage"]["file_formats"]:
        print("  File formats:")
        for fmt, count in stats["storage"]["file_formats"].items():
            print(f"    - {fmt}: {count} files")

    print(f"  Available APIs: {', '.join(stats['api_sources'])}")


def cmd_cleanup(args):
    """Handle cleanup command"""
    crawler = BoxHuntCrawler()
    result = crawler.cleanup()

    print("\n🧹 Cleanup completed:")
    print(f"  Orphaned files removed: {result['orphaned_files_removed']}")
    print(f"  Failed URLs cleared: {result['failed_urls_cleared']}")


def cmd_export(args):
    """Handle export command"""
    crawler = BoxHuntCrawler()
    output_file = crawler.export_results(format=args.format)

    if output_file:
        print(f"\n📄 Metadata exported to: {output_file}")
    else:
        print("\n❌ Export failed")


def cmd_gen(args):
    """Handle gen command"""
    import json
    from datetime import datetime
    from pathlib import Path

    import replicate

    # Check if Replicate API token is available
    if not Config.REPLICATE_API_TOKEN:
        print("❌ Replicate API token not found!")
        print(
            "💡 Please set REPLICATE_API_TOKEN in your .env file or environment variables"
        )
        print("   Get your token from: https://replicate.com/account/api-tokens")
        sys.exit(1)

    print(f"🎨 Generating {args.count} images using Replicate AI...")

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("data") / f"replicate_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prepare the prompt
    prompt = """A high-quality product photo showing exactly four fully closed packaging boxes arranged in a 2x2 grid layout, positioned in the top-left, top-right, bottom-left, and bottom-right areas of the image.
Each box is shown in a balanced three-quarter perspective with a moderate viewing angle, so the front, side, and top surfaces are all clearly visible and proportionally displayed.
Boxes are made of corrugated paper, with colorful CMYK-printed graphics, brand logos, and detailed product designs, featuring vibrant colors, bold typography, illustrated patterns, photographic imagery, and product information panels"""

    # Generation parameters
    generation_params = {
        "prompt": prompt,
        "go_fast": False,
        "megapixels": "1",
        "num_outputs": 1,
        "aspect_ratio": "1:1",
        "output_format": "jpg",
        "output_quality": 95,
        "num_inference_steps": 4,
    }

    try:
        print("🚀 Starting image generation...")

        # Calculate how many requests we need
        max_outputs_per_request = 4
        total_requests = (
            args.count + max_outputs_per_request - 1
        ) // max_outputs_per_request

        saved_images = []
        image_counter = 1

        for request_num in range(total_requests):
            # Calculate how many images to generate in this request
            images_in_this_request = min(
                max_outputs_per_request,
                args.count - request_num * max_outputs_per_request,
            )

            print(
                f"📦 Request {request_num + 1}/{total_requests}: Generating {images_in_this_request} images..."
            )

            # Update generation parameters for this request
            request_params = generation_params.copy()
            request_params["num_outputs"] = images_in_this_request

            output = replicate.run(
                "black-forest-labs/flux-schnell", input=request_params
            )

            # Save images from this request
            for image in output:
                # Generate filename
                filename = f"generated_box_{image_counter:03d}.jpg"
                filepath = output_dir / filename

                # Download and save image
                with open(filepath, "wb") as f:
                    f.write(image.read())

                saved_images.append(
                    {
                        "filename": filename,
                        "url": image.url,
                        "index": image_counter,
                        "request_number": request_num + 1,
                    }
                )

                print(f"✅ Saved: {filename}")
                image_counter += 1

        # Save metadata
        metadata = {
            "generation_timestamp": timestamp,
            "generation_params": generation_params,
            "total_images": len(saved_images),
            "total_requests": total_requests,
            "max_outputs_per_request": max_outputs_per_request,
            "output_directory": str(output_dir),
            "images": saved_images,
        }

        metadata_file = output_dir / "generation_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as metadata_f:
            json.dump(metadata, metadata_f, indent=2, ensure_ascii=False)

        print("\n🎉 Generation completed successfully!")
        print(f"📁 Output directory: {output_dir}")
        print(f"📊 Generated {len(saved_images)} images")
        print(f"📄 Metadata saved to: {metadata_file}")

    except Exception as e:
        print(f"❌ Generation failed: {e}")
        logging.error(f"Image generation failed: {e}")
        sys.exit(1)


def cmd_gui(args):
    """Handle GUI command"""
    try:
        from .gui_main import main as gui_main

        print("🎨 Starting BoxHunt GUI...")
        sys.exit(gui_main())
    except ImportError as e:
        print("❌ GUI dependencies not available:")
        print(f"   {e}")
        print("\n💡 Install GUI dependencies:")
        print("   uv sync  # This should install all dependencies including GUI ones")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting GUI: {e}")
        sys.exit(1)


async def cmd_crawl_site(args):
    """Handle crawl-site command"""
    from urllib.parse import urlparse

    from .image_processor import ImageProcessor
    from .storage import StorageManager
    from .website_client import WebsiteClient

    # Extract domain name from URL
    parsed_url = urlparse(args.url)
    domain_name = parsed_url.netloc.lower()
    if domain_name.startswith("www."):
        domain_name = domain_name[4:]
    domain_name = domain_name.split(":")[0]  # Remove port if exists

    print(f"🌐 开始爬取网站: {args.url}")
    print(f"   域名: {domain_name}")
    print(f"   最大图片数: {args.max_images}")
    print(
        f"   爬取深度: {args.depth if hasattr(args, 'depth') else Config.MAX_SCRAPING_DEPTH}"
    )

    # Initialize components for website crawling with domain-specific storage
    website_client = WebsiteClient(
        respect_robots=args.respect_robots
        if hasattr(args, "respect_robots")
        else Config.RESPECT_ROBOTS_TXT,
        max_depth=args.depth if hasattr(args, "depth") else Config.MAX_SCRAPING_DEPTH,
    )

    image_processor = ImageProcessor(domain_name=domain_name)
    storage_manager = StorageManager(domain_name=domain_name)

    # Load existing hashes for deduplication
    image_processor.downloaded_hashes = storage_manager.get_existing_hashes()

    try:
        # Scrape images from website
        search_results = await website_client.scrape_website(args.url, args.max_images)

        if not search_results:
            print("❌ 未找到任何图片")
            return

        print(f"🔍 发现 {len(search_results)} 个图片链接")

        # Process images (download, validate, deduplicate)
        from tqdm.asyncio import tqdm

        processed_results = []
        pbar = tqdm(total=len(search_results), desc="处理图片", unit="img")

        batch_size = max(
            1, min(Config.MAX_CONCURRENT_REQUESTS, len(search_results) // 10)
        )

        for i in range(0, len(search_results), batch_size):
            batch = search_results[i : i + batch_size]
            batch_results = await image_processor.process_image_batch(batch)
            processed_results.extend(batch_results)
            pbar.update(len(batch))

        pbar.close()

        # Save metadata
        saved_count = 0
        if processed_results:
            if storage_manager.save_image_metadata(processed_results):
                saved_count = len(processed_results)

        print("✅ 网站爬取完成:")
        print(f"   发现图片: {len(search_results)}")
        print(f"   成功下载: {saved_count}")
        print(f"   保存位置: {Config.get_domain_images_dir(domain_name)}")
        print(f"   元数据文件: {Config.get_domain_metadata_file(domain_name)}")

    except Exception as e:
        logging.error(f"Website crawling failed: {e}")
        print(f"❌ 爬取失败: {e}")


def cmd_config(args):
    """Handle config command"""
    print("\n⚙️  Current Configuration:")
    print(f"  Data directory: {Config.DATA_DIR}")
    print("  Storage: Domain-based (data/{domain_name}/)")
    print(f"  Min image size: {Config.MIN_IMAGE_WIDTH}×{Config.MIN_IMAGE_HEIGHT}")
    print(f"  Max file size: {Config.MAX_FILE_SIZE / (1024 * 1024):.1f} MB")
    print(f"  Request delay: {Config.REQUEST_DELAY}s")
    print(f"  Max concurrent: {Config.MAX_CONCURRENT_REQUESTS}")

    api_keys = Config.validate_api_keys()
    print("\n🔑 API Keys Status:")
    for api, available in api_keys.items():
        status = "✓ Available" if available else "✗ Missing"
        print(f"  {api}: {status}")

    print(f"\n🔍 Search Keywords ({len(Config.get_all_keywords())} total):")
    print(
        f"  English: {', '.join(Config.KEYWORDS_EN[:5])}{'...' if len(Config.KEYWORDS_EN) > 5 else ''}"
    )
    print(
        f"  Chinese: {', '.join(Config.KEYWORDS_CN[:3])}{'...' if len(Config.KEYWORDS_CN) > 3 else ''}"
    )


def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="BoxHunt - Cardboard Box Image Web Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Crawl command
    crawl_parser = subparsers.add_parser("crawl", help="Start crawling for images")
    crawl_parser.add_argument(
        "--keywords",
        type=str,
        help="Comma-separated keywords (default: use all predefined)",
    )
    crawl_parser.add_argument(
        "--max-images",
        type=int,
        default=20,
        help="Max images per source per keyword (default: 20)",
    )
    crawl_parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between keywords in seconds (default: 1.0)",
    )
    crawl_parser.add_argument(
        "--sources",
        type=str,
        help='Comma-separated API sources (e.g. "pexels", default: all available)',
    )

    # Crawl-site command
    crawl_site_parser = subparsers.add_parser(
        "crawl-site", help="Crawl images from a specific website"
    )
    crawl_site_parser.add_argument(
        "url", type=str, help="Website URL to crawl for images"
    )
    crawl_site_parser.add_argument(
        "--max-images",
        type=int,
        default=Config.MAX_IMAGES_PER_WEBSITE,
        help=f"Maximum images to download (default: {Config.MAX_IMAGES_PER_WEBSITE})",
    )
    crawl_site_parser.add_argument(
        "--depth",
        type=int,
        default=Config.MAX_SCRAPING_DEPTH,
        help=f"Maximum crawling depth (default: {Config.MAX_SCRAPING_DEPTH})",
    )
    crawl_site_parser.add_argument(
        "--respect-robots", action="store_true", help="Respect robots.txt restrictions"
    )

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume interrupted crawl")
    resume_parser.add_argument(
        "--keywords",
        type=str,
        help="Comma-separated keywords (default: use all predefined)",
    )
    resume_parser.add_argument(
        "--max-images",
        type=int,
        default=20,
        help="Max images per source per keyword (default: 20)",
    )
    resume_parser.add_argument(
        "--sources",
        type=str,
        help='Comma-separated API sources (e.g. "pexels", default: all available)',
    )

    # Test command
    subparsers.add_parser("test", help="Test API connections")

    # Stats command
    subparsers.add_parser("stats", help="Show collection statistics")

    # Cleanup command
    subparsers.add_parser("cleanup", help="Clean up orphaned files")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export metadata")
    export_parser.add_argument(
        "--format",
        choices=["csv", "json", "xlsx"],
        default="csv",
        help="Export format (default: csv)",
    )

    # Config command
    subparsers.add_parser("config", help="Show current configuration")

    # GUI command
    subparsers.add_parser("gui", help="Launch the 3D box creation GUI")

    # Gen command
    gen_parser = subparsers.add_parser("gen", help="Generate images using Replicate AI")
    gen_parser.add_argument(
        "--count",
        type=int,
        default=3,
        help="Number of images to generate (default: 3)",
    )

    return parser


def main():
    """Main entry point"""
    print_banner()

    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Setup logging
    setup_logging(args.log_level)

    async def run_async_command():
        try:
            if args.command == "crawl":
                await cmd_crawl(args)
            elif args.command == "crawl-site":
                await cmd_crawl_site(args)
            elif args.command == "resume":
                await cmd_resume(args)
            elif args.command == "test":
                await cmd_test(args)
            elif args.command == "stats":
                cmd_stats(args)
            elif args.command == "cleanup":
                cmd_cleanup(args)
            elif args.command == "export":
                cmd_export(args)
            elif args.command == "config":
                cmd_config(args)
            elif args.command == "gui":
                cmd_gui(args)
            elif args.command == "gen":
                cmd_gen(args)
            else:
                print(f"Unknown command: {args.command}")
                parser.print_help()

        except KeyboardInterrupt:
            print("\n\n⚠️  Crawl interrupted by user")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            print(f"\n❌ Error: {e}")
            sys.exit(1)

    # Run async commands if needed
    if args.command in ["crawl", "crawl-site", "resume", "test"]:
        asyncio.run(run_async_command())
    else:
        # Run sync commands directly
        try:
            if args.command == "stats":
                cmd_stats(args)
            elif args.command == "cleanup":
                cmd_cleanup(args)
            elif args.command == "export":
                cmd_export(args)
            elif args.command == "config":
                cmd_config(args)
            elif args.command == "gui":
                cmd_gui(args)
            elif args.command == "gen":
                cmd_gen(args)
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            print(f"\n❌ Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
