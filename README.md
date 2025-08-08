# BoxHunt - 纸箱图像网络爬虫

BoxHunt是一个专门用于收集互联网上纸箱图像的网络爬虫工具。它支持多个图像API源，具备自动去重、质量控制和结构化存储功能。

## 特性

- 🎯 **多源搜索**: 支持 Unsplash、Pexels API
- 🔍 **智能关键词**: 内置中英文纸箱相关关键词库
- 🖼️ **质量控制**: 自动过滤图片尺寸、格式和文件大小
- 🚫 **智能去重**: 基于感知哈希的图像去重算法
- 💾 **结构化存储**: CSV元数据管理 + 文件系统存储
- ⚡ **异步处理**: 高效的并发下载和处理
- 🔄 **断点续传**: 支持中断后继续爬取
- 📊 **统计分析**: 详细的收集统计信息

## 安装

### 使用 uv (推荐)

```bash
# 克隆仓库
git clone https://github.com/yourusername/BoxHunt.git
cd BoxHunt

# 使用uv安装依赖
uv pip install -e .
```

### 传统方式

```bash
pip install -e .
```

## 配置

1. 复制环境变量模板:
```bash
cp env.example .env
```

2. 编辑 `.env` 文件，添加API密钥:
```env
# Unsplash API  
UNSPLASH_ACCESS_KEY=your_unsplash_access_key_here

# Pexels API
PEXELS_API_KEY=your_pexels_api_key_here
```

### API密钥获取

- **Unsplash API**: [Unsplash开发者页面](https://unsplash.com/developers)  
- **Pexels API**: [Pexels API页面](https://www.pexels.com/api/)

## 使用方法

### 基本命令

```bash
# 查看配置信息
boxhunt config

# 测试API连接
boxhunt test

# 开始爬取 (使用所有预定义关键词)
boxhunt crawl

# 使用自定义关键词爬取
boxhunt crawl --keywords "cardboard box,shipping box"

# 设置每个源每个关键词的最大图片数
boxhunt crawl --max-images 50

# 恢复中断的爬取任务
boxhunt resume

# 查看收集统计
boxhunt stats

# 清理孤立文件
boxhunt cleanup

# 导出元数据
boxhunt export --format json
```

### Python API 使用

```python
import asyncio
from boxhunt import BoxHuntCrawler

async def main():
    # 创建爬虫实例
    crawler = BoxHuntCrawler()
    
    # 测试API连接
    test_results = await crawler.test_apis()
    print(test_results)
    
    # 爬取单个关键词
    result = await crawler.crawl_single_keyword("cardboard box", max_images_per_source=30)
    print(f"Saved {result['saved_images']} images")
    
    # 爬取多个关键词
    results = await crawler.crawl_multiple_keywords(
        keywords=["纸箱", "瓦楞纸箱"], 
        max_images_per_source=20
    )
    
    # 获取统计信息
    stats = crawler.get_statistics()
    print(stats)

if __name__ == "__main__":
    asyncio.run(main())
```

## 项目结构

```
BoxHunt/
├── boxhunt/                 # 主要源代码
│   ├── __init__.py
│   ├── config.py           # 配置管理
│   ├── api_clients.py      # API客户端
│   ├── image_processor.py  # 图像处理
│   ├── storage.py          # 存储管理
│   ├── crawler.py          # 主爬虫类
│   └── main.py             # 命令行入口
├── data/                   # 数据目录
│   ├── images/            # 下载的图片
│   ├── cache/             # 缓存文件  
│   └── metadata.csv       # 元数据
├── pyproject.toml         # 项目配置
├── env.example            # 环境变量模板
└── README.md              # 项目说明
```

## 配置选项

### 搜索关键词

默认关键词包括:
- **英文**: cardboard box, corrugated box, carton, shipping box, moving box 等
- **中文**: 纸箱, 瓦楞纸箱, 搬家箱, 快递箱, 包装箱 等

### 图像过滤

- **最小尺寸**: 256×256 像素
- **支持格式**: JPG, PNG, WebP
- **最大文件**: 10MB
- **质量控制**: 自动验证图像完整性

### 性能设置  

- **并发请求**: 最多3个同时请求
- **请求间隔**: 默认1秒
- **重试次数**: 失败后最多重试3次
- **去重算法**: 感知哈希 + 汉明距离

## 合规性说明

本工具遵循以下合规原则:

1. **API优先**: 优先使用官方API而非直接爬取网页
2. **速率限制**: 内置请求间隔，避免对服务器造成压力
3. **许可遵守**: 仅使用有明确使用许可的图像源
4. **robots.txt**: 如需直接爬取，会先检查robots.txt
5. **用户代理**: 使用标识明确的User-Agent

## 数据格式

### 元数据 CSV 字段

| 字段 | 描述 |
|------|------|
| id | 唯一标识符 |
| filename | 本地文件名 |
| url | 原始图片URL |
| source | 来源API (unsplash/pexels) |
| title | 图片标题/描述 |
| width | 图片宽度 |
| height | 图片高度 |
| file_size | 文件大小(字节) |
| perceptual_hash | 感知哈希值 |
| download_time | 下载时间戳 |
| created_at | 记录创建时间 |
| status | 状态 (downloaded) |

## 故障排除

### 常见问题

1. **No API clients available**
   - 检查 `.env` 文件是否存在且包含有效API密钥
   - 运行 `boxhunt config` 查看API密钥状态

2. **Images not downloading**
   - 检查网络连接
   - 运行 `boxhunt test` 测试API连接
   - 查看日志文件 `boxhunt.log`

3. **Permission errors**
   - 确保对 `data/` 目录有写权限
   - 检查磁盘空间是否充足

### 日志

应用会在以下位置记录日志:
- 控制台输出 (实时)
- `boxhunt.log` 文件 (持久化)

设置日志级别:
```bash
boxhunt --log-level DEBUG crawl
```

## 贡献

欢迎贡献代码! 请遵循以下步骤:

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 免责声明

- 请确保遵守目标网站的服务条款和 robots.txt
- 仅用于合法的研究和个人用途
- 用户需自行承担使用本工具的责任
- 请尊重版权，仅收集有适当授权的图像