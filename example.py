#!/usr/bin/env python3
"""
BoxHunt使用示例
"""

import asyncio
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from boxhunt.config import Config
from boxhunt.crawler import BoxHuntCrawler


async def basic_example():
    """基础使用示例"""
    print("🚀 BoxHunt基础示例")

    # 创建爬虫实例
    crawler = BoxHuntCrawler()

    # 检查API配置
    print("\n1. 检查API配置...")
    stats = crawler.get_statistics()
    available_apis = stats["api_sources"]

    if not available_apis:
        print("❌ 没有可用的API源，请检查.env文件中的API密钥配置")
        print("   参考env.example文件进行配置")
        return

    print(f"✅ 可用API源: {', '.join(available_apis)}")

    # 测试API连接
    print("\n2. 测试API连接...")
    test_results = await crawler.test_apis()

    for source, result in test_results.items():
        if result["status"] == "success":
            print(f"✅ {source}: {result['results_count']} 个测试结果")
        else:
            print(f"❌ {source}: {result['error']}")

    # 爬取少量图片进行测试
    print("\n3. 测试爬取 (每个源最多5张图片)...")
    result = await crawler.crawl_single_keyword(
        "cardboard box", max_images_per_source=5
    )

    print("📊 爬取结果:")
    print(f"   找到图片: {result['found_images']}")
    print(f"   处理成功: {result['processed_images']}")
    print(f"   保存图片: {result['saved_images']}")


async def advanced_example():
    """高级使用示例"""
    print("\n🔥 BoxHunt高级示例")

    crawler = BoxHuntCrawler()

    # 使用自定义关键词列表
    custom_keywords = ["cardboard box", "纸箱", "corrugated box"]

    print(f"\n使用自定义关键词: {custom_keywords}")

    # 批量爬取
    results = await crawler.crawl_multiple_keywords(
        keywords=custom_keywords,
        max_images_per_source=10,
        delay_between_keywords=0.5,  # 关键词间隔0.5秒
    )

    print("\n📈 批量爬取结果:")
    print(f"   处理关键词: {results['completed_keywords']}/{results['total_keywords']}")
    print(f"   找到图片总数: {results['total_found_images']}")
    print(f"   保存图片总数: {results['total_saved_images']}")

    # 显示每个关键词的详细结果
    print("\n📝 详细结果:")
    for keyword_result in results["keyword_results"]:
        print(
            f"   '{keyword_result['keyword']}': {keyword_result['saved_images']} 张保存"
        )

    # 显示统计信息
    stats = crawler.get_statistics()
    storage_stats = stats["storage"]

    print("\n📊 收集统计:")
    print(f"   总图片数: {storage_stats['total_images']}")
    print(f"   总大小: {storage_stats['total_size'] / (1024 * 1024):.2f} MB")
    print(f"   平均尺寸: {storage_stats['avg_width']}×{storage_stats['avg_height']}")

    if storage_stats["sources"]:
        print("   各源统计:")
        for source, count in storage_stats["sources"].items():
            print(f"     {source}: {count} 张")


async def resume_example():
    """断点续传示例"""
    print("\n🔄 断点续传示例")

    crawler = BoxHuntCrawler()

    print("模拟恢复中断的爬取任务...")

    # 恢复爬取 (会自动跳过已下载的图片)
    result = await crawler.resume_crawl(
        keywords=["shipping box", "包装箱"], max_images_per_source=15
    )

    print("恢复爬取完成:")
    print(f"  新保存图片: {result['total_saved_images']}")


def management_example():
    """管理功能示例"""
    print("\n🛠️ 管理功能示例")

    crawler = BoxHuntCrawler()

    # 获取统计信息
    print("1. 获取统计信息...")
    stats = crawler.get_statistics()
    print(f"   当前收藏: {stats['storage']['total_images']} 张图片")

    # 清理孤立文件
    print("\n2. 清理孤立文件...")
    cleanup_result = crawler.cleanup()
    print(f"   清理孤立文件: {cleanup_result['orphaned_files_removed']}")
    print(f"   清理失败URL: {cleanup_result['failed_urls_cleared']}")

    # 导出元数据
    print("\n3. 导出元数据...")
    export_file = crawler.export_results(format="json")
    if export_file:
        print(f"   元数据已导出到: {export_file}")


async def main():
    """主函数"""
    try:
        print("=" * 50)
        print("   BoxHunt 纸箱图像爬虫示例程序")
        print("=" * 50)

        # 检查配置
        api_keys = Config.validate_api_keys()
        if not any(api_keys.values()):
            print("\n⚠️  警告: 没有检测到API密钥")
            print("请复制 env.example 到 .env 并配置API密钥")
            print("\nAPI密钥状态:")
            for api, available in api_keys.items():
                status = "✅" if available else "❌"
                print(f"  {status} {api}")

            response = input("\n是否继续运行示例? (y/N): ")
            if response.lower() != "y":
                return

        # 运行示例
        await basic_example()

        print("\n" + "=" * 30)
        response = input("是否继续运行高级示例? (y/N): ")
        if response.lower() == "y":
            await advanced_example()

        print("\n" + "=" * 30)
        response = input("是否运行断点续传示例? (y/N): ")
        if response.lower() == "y":
            await resume_example()

        print("\n" + "=" * 30)
        response = input("是否运行管理功能示例? (y/N): ")
        if response.lower() == "y":
            management_example()

        print("\n🎉 示例程序运行完成!")
        print("\n💡 提示:")
        print("  - 使用 'boxhunt config' 查看完整配置")
        print("  - 使用 'boxhunt crawl --help' 查看所有选项")
        print("  - 查看 data/ 目录下的下载文件")

    except KeyboardInterrupt:
        print("\n\n⚠️ 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
