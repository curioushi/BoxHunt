# BoxHunt GUI 部署指南

本文档介绍如何使用 pyside6-deploy 将 BoxHunt 的 GUI 部分打包为独立可执行文件。

## 依赖安装

首先安装打包所需的依赖：

```bash
uv add --dev nuitka ordered-set zstandard patchelf pip
```

## 打包步骤

1. 确保在项目根目录下运行：
```bash
cd /path/to/BoxHunt
```

2. 使用配置文件进行打包：
```bash
uv run pyside6-deploy -c boxhunt/pysidedeploy.spec
```

## 配置说明

`boxhunt/pysidedeploy.spec` 文件的主要配置：

- **input_file**: `boxhunt/gui_main.py` - GUI 入口文件（相对路径）
- **exec_directory**: `.` - 输出到项目根目录
- **mode**: `onefile` - 打包为单个可执行文件
- **excluded modules**: 排除了爬虫相关模块，只包含 GUI 功能

### 关键配置项

```ini
[app]
title = BoxHunt
input_file = boxhunt/gui_main.py
exec_directory = .

[nuitka]
mode = onefile
extra_args = --quiet --noinclude-qt-translations --nofollow-import-to=boxhunt.crawler --nofollow-import-to=boxhunt.website_client --nofollow-import-to=boxhunt.api_clients --nofollow-import-to=aiohttp --nofollow-import-to=asyncio-throttle --nofollow-import-to=beautifulsoup4 --nofollow-import-to=lxml --nofollow-import-to=OpenGL_accelerate --include-module=boxhunt.gui --include-module=boxhunt.box3d
```

## 生成结果

成功打包后，会在项目根目录生成：
- `BoxHunt.bin` - 约 58MB 的独立可执行文件

## 运行方式

```bash
./BoxHunt.bin
```

## 注意事项

1. 使用相对路径配置，便于在不同环境中使用
2. 排除了爬虫相关模块，大幅减小文件大小
3. 包含了完整的 GUI 功能和 3D 渲染能力
4. 生成的可执行文件不依赖 Python 环境，可直接分发

## 故障排除

如果遇到 OpenGL 相关错误，已在配置中排除了 `OpenGL_accelerate` 模块。
如果需要调试，可以添加 `--verbose` 参数：

```bash
uv run pyside6-deploy -c boxhunt/pysidedeploy.spec --verbose
```
