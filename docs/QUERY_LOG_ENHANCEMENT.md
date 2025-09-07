# 查询日志增强功能

本文档介绍{{ project_name }}管理系统新增的查询日志增强功能，包括高级搜索、日志导出、AI分析等特性。

## 功能概述

### 1. 高级日志搜索
- **多条件过滤**: 支持域名、客户端IP、查询类型、响应代码、阻止状态等多种过滤条件
- **时间范围**: 可指定查询的时间范围
- **组合搜索**: 支持多个条件的组合搜索
- **实时搜索**: 搜索结果实时更新

### 2. 日志导出功能
- **多格式支持**: 支持CSV和JSON两种导出格式
- **过滤导出**: 可基于搜索条件导出特定日志
- **异步处理**: 大量数据导出采用后台异步处理
- **状态跟踪**: 实时跟踪导出任务状态和进度

### 3. 日志分析报告
- **趋势分析**: 生成DNS查询趋势分析报告
- **统计图表**: 提供可视化的统计图表
- **多时间维度**: 支持小时、天、周、月等不同时间维度分析
- **热门域名**: 统计最常访问的域名

### 4. AI智能分析
- **DeepSeek集成**: 集成DeepSeek AI进行智能域名分析
- **威胁识别**: 自动识别广告、追踪器、恶意软件等威胁
- **智能推荐**: 基于AI分析结果提供阻止建议
- **批量分析**: 支持批量分析多个域名
- **审核流程**: 管理员可审核AI分析结果并采取行动

## 技术架构

### 后端服务

#### QueryLogService
- **位置**: `app/services/query_log_service.py`
- **功能**: 提供高级搜索、导出、分析报告等核心功能
- **主要方法**:
  - `advanced_search()`: 高级搜索功能
  - `export_logs()`: 日志导出功能
  - `generate_analysis_report()`: 生成分析报告

#### AIAnalysisService
- **位置**: `app/services/ai_analysis_service.py`
- **功能**: DeepSeek AI集成和域名分析
- **主要方法**:
  - `analyze_domain()`: 单个域名分析
  - `batch_analyze()`: 批量域名分析
  - `get_pending_reviews()`: 获取待审核结果
  - `review_analysis()`: 审核分析结果

### 数据模型

#### QueryLogAnalysis
- **位置**: `app/models/query_log_analysis.py`
- **功能**: 存储AI分析结果
- **字段**:
  - `domain`: 域名
  - `analysis_type`: 分析类型（ad/tracker/malware/legitimate）
  - `confidence`: 置信度
  - `recommendation`: 推荐操作
  - `reviewed`: 是否已审核

#### QueryLogExport
- **位置**: `app/models/query_log_analysis.py`
- **功能**: 记录导出任务
- **字段**:
  - `export_type`: 导出格式
  - `filters`: 过滤条件
  - `status`: 任务状态
  - `file_path`: 文件路径

### 前端界面

#### 增强查询日志页面
- **位置**: `app/templates/admin/query_log_enhanced.html`
- **功能**: 集成所有增强功能的主界面
- **特性**:
  - 响应式设计
  - 实时数据更新
  - 模态框交互
  - 图表可视化

#### AI分析配置页面
- **位置**: `app/templates/admin/ai_analysis_config.html`
- **功能**: AI分析功能的配置和管理
- **特性**:
  - API密钥配置
  - 自动分析开关
  - 分析阈值设置
  - 待审核结果管理

## API接口

### 查询日志相关

```
GET  /admin/api/query-log/advanced-search    # 高级搜索
POST /admin/api/query-log/export            # 导出日志
GET  /admin/api/query-log/analysis-report   # 分析报告
```

### AI分析相关

```
POST /admin/api/ai-analysis/domain          # 单个域名分析
POST /admin/api/ai-analysis/domains/batch   # 批量域名分析
GET  /admin/api/ai-analysis/pending-reviews # 待审核列表
POST /admin/api/ai-analysis/review          # 审核分析结果
GET  /admin/api/ai-analysis/stats           # 分析统计
GET  /admin/api/ai-analysis/config          # 获取配置
POST /admin/api/ai-analysis/config          # 保存配置
```

## 配置说明

### DeepSeek API配置

1. **获取API密钥**:
   - 访问 [DeepSeek平台](https://platform.deepseek.com/)
   - 注册账号并获取API密钥

2. **配置步骤**:
   - 进入「AI分析配置」页面
   - 输入DeepSeek API密钥
   - 设置自动分析开关
   - 调整分析阈值
   - 测试API连接

3. **配置参数**:
   - `deepseek_api_key`: DeepSeek API密钥
   - `auto_analysis_enabled`: 是否启用自动分析
   - `analysis_threshold`: 分析置信度阈值（0.1-1.0）

## 使用指南

### 高级搜索

1. 进入「增强查询日志」页面
2. 点击「高级搜索」按钮
3. 设置搜索条件：
   - 域名：支持模糊匹配
   - 客户端：IP地址过滤
   - 查询类型：A、AAAA、CNAME等
   - 响应代码：HTTP状态码
   - 阻止状态：已阻止/已允许
   - 时间范围：开始和结束时间
4. 点击「搜索」执行查询

### 日志导出

1. 在查询日志页面点击「导出日志」
2. 选择导出格式（CSV或JSON）
3. 设置过滤条件（可选）
4. 点击「开始导出」
5. 等待导出完成并下载文件

### AI域名分析

1. **单个域名分析**:
   - 在日志表格中点击域名
   - 选择「AI分析」
   - 查看分析结果

2. **批量分析**:
   - 点击「AI分析」按钮
   - 选择要分析的域名
   - 等待分析完成

3. **审核分析结果**:
   - 进入「AI分析配置」页面
   - 查看待审核列表
   - 选择允许、阻止或忽略
   - 添加审核备注

## 安全考虑

1. **API密钥安全**:
   - API密钥加密存储
   - 支持密钥可见性切换
   - 定期更换API密钥

2. **数据隐私**:
   - 域名数据仅用于分析
   - 不存储敏感查询内容
   - 支持分析结果删除

3. **访问控制**:
   - 仅管理员可访问AI分析功能
   - 审核操作记录日志
   - 支持权限细分

## 性能优化

1. **数据库优化**:
   - 添加必要的索引
   - 分页查询减少内存占用
   - 定期清理过期数据

2. **异步处理**:
   - 大量数据导出异步处理
   - AI分析任务队列化
   - 避免阻塞主线程

3. **缓存策略**:
   - 分析结果缓存
   - 统计数据缓存
   - 减少重复计算

## 故障排除

### 常见问题

1. **API连接失败**:
   - 检查API密钥是否正确
   - 确认网络连接正常
   - 查看错误日志详情

2. **导出失败**:
   - 检查磁盘空间是否充足
   - 确认导出目录权限
   - 查看任务状态和错误信息

3. **搜索结果为空**:
   - 检查搜索条件是否过于严格
   - 确认时间范围设置
   - 验证{{ project_name }}连接状态

### 日志查看

- 应用日志：`logs/app.log`
- 错误日志：`logs/error.log`
- AI分析日志：查看数据库`query_log_analysis`表

## 更新日志

### v1.0.0 (2024-01-01)
- 新增高级日志搜索功能
- 新增日志导出功能（CSV/JSON）
- 新增DNS查询趋势分析报告
- 集成DeepSeek AI智能域名分析
- 新增AI分析配置和审核功能
- 优化用户界面和交互体验

## 技术支持

如有问题或建议，请通过以下方式联系：

- 项目Issues：提交GitHub Issues
- 技术文档：查看项目Wiki
- 社区讨论：参与项目讨论区

---

*本文档将随功能更新持续维护，请关注最新版本。*