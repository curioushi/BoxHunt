# 🔒 BoxHunt 安全配置指南

本指南帮助你配置安全设置，防止敏感信息（如API密钥）被IDE或其他工具扫描和上传。

## 🛡️ IDE 保护配置

### Cursor 特定设置

项目已经配置了以下保护措施：

1. **`.cursor/settings.json`** - Cursor特定配置
2. **`.vscode/settings.json`** - VS Code兼容配置
3. **`.cursorignore`** - Cursor忽略文件

### 手动验证步骤

1. **检查文件排除设置**：
   - 打开 Cursor 设置 (Ctrl/Cmd + ,)
   - 搜索 "files.exclude"
   - 确认 `.env` 文件被排除

2. **验证搜索排除**：
   - 使用 Ctrl/Cmd + Shift + F 全局搜索
   - 搜索框右侧点击设置图标
   - 确认 "search.exclude" 包含 `.env` 模式

## 🚫 Cursor AI 功能控制

### 禁用代码上传到云端

在 Cursor 设置中配置：

```json
{
  "cursor.general.enableLogging": false,
  "cursor.general.enableTelemetry": false,
  "cursor.cpp.enableTelemetry": false,
  "cursor.python.enableTelemetry": false
}
```

### 配置私有模式

1. **Settings > Cursor > Privacy**：
   - ✅ Disable telemetry
   - ✅ Disable logging
   - ✅ Private mode for sensitive projects

2. **禁用自动补全上传**：
   - Settings > Cursor > Features
   - 关闭 "Upload code context for better suggestions"

## 📁 文件系统保护

### 当前配置的排除模式

以下文件/目录已被排除：

```
# 环境文件
.env
.env.*
*.env

# 敏感配置
*.key
*.pem
secrets/
*api_key*
*secret*
*token*

# 缓存和日志
.cache/
*.log
```

### 验证排除状态

```bash
# 检查.env文件是否被Git忽略
git status --ignored

# 验证.env文件不在跟踪中
git ls-files | grep -E "\.env"
```

## 🔐 API 密钥安全最佳实践

### 1. 环境变量命名

使用清晰的命名约定：

```env
# ✅ 好的命名
UNSPLASH_ACCESS_KEY=your_key_here
PEXELS_API_KEY=your_key_here

# ❌ 避免的命名
KEY=your_key_here
SECRET=your_key_here
```

### 2. 密钥权限限制

- **Unsplash**: 确保只申请需要的权限 (public scope)
- **Pexels**: 使用只读权限
- 定期轮换API密钥

### 3. 密钥存储

```bash
# 设置文件权限 (Unix/Linux)
chmod 600 .env

# 验证权限
ls -la .env
```

## 🚨 泄露检测与响应

### 检查意外提交

```bash
# 搜索历史提交中的敏感信息
git log -p | grep -E "(api_key|secret|token|password)"

# 检查当前暂存区
git diff --cached | grep -E "(api_key|secret|token)"
```

### 如果密钥泄露

1. **立即撤销API密钥**
2. **生成新的密钥**
3. **更新.env文件**
4. **清理Git历史** (如果已提交)：

```bash
# 从历史中删除文件 (谨慎使用)
git filter-branch --force --index-filter \
'git rm --cached --ignore-unmatch .env' \
--prune-empty --tag-name-filter cat -- --all
```

## 📋 安全检查清单

### 项目设置
- [ ] `.env` 文件在 `.gitignore` 中
- [ ] IDE 配置排除 `.env` 文件
- [ ] 禁用了代码上传功能
- [ ] 设置了合适的文件权限

### 开发流程
- [ ] 从不在代码中硬编码密钥
- [ ] 定期轮换API密钥
- [ ] 使用最小权限原则
- [ ] 定期检查提交历史

### Cursor 特定
- [ ] 禁用遥测和日志
- [ ] 配置私有模式
- [ ] 验证文件排除工作正常
- [ ] 关闭自动代码上传

## 🆘 紧急情况处理

如果怀疑密钥泄露：

1. **立即操作**：
   ```bash
   # 备份当前配置
   cp .env .env.backup
   
   # 清空敏感文件
   echo "# API keys - please reconfigure" > .env
   ```

2. **联系API提供商**：
   - Unsplash: https://unsplash.com/developers
   - Pexels: https://www.pexels.com/api/

3. **重新配置**：
   - 生成新的API密钥
   - 更新项目配置
   - 测试功能正常

## 💡 额外建议

- 考虑使用环境变量管理工具 (如 `direnv`)
- 在CI/CD中使用加密的秘密管理
- 定期进行安全审计
- 团队开发时使用共享的密钥管理系统