# AdGuardHome 管理系统 (ADGHM)

## 项目介绍

AdGuardHome 管理系统（ADGHM）是一个基于 Flask 的 Web 应用程序，旨在简化 AdGuardHome 的管理和配置过程。该系统提供了用户友好的界面，允许多用户管理各自的 AdGuardHome 客户端，并通过阿里云域名解析服务自动更新动态 IP 地址。

![用户主页](/app/static/images/user_dashboard.svg)

### 主要功能

1. **多用户管理**：支持多用户注册和登录，每个用户可以管理自己的 AdGuardHome 客户端。

2. **AdGuardHome 客户端管理**：
   - 创建和管理 AdGuardHome 客户端
   - 配置客户端过滤规则
   - 查看客户端状态和统计信息
   
   ![客户端管理](/app/static/images/client_management.svg)

3. **动态域名解析**：
   - 自动检测公网 IP 变化（支持 IPv4 和 IPv6）
   - 通过阿里云 DNS 服务自动更新域名解析记录
   - 为每个客户端分配唯一的子域名
   
   ![域名管理](/app/static/images/domain_management.svg)

4. **系统管理**：
   - 管理员后台用于系统配置和用户管理
   - 操作日志记录和查看
   - AdGuardHome API 配置管理
   
   ![管理员后台](/app/static/images/admin_dashboard.svg)

## 系统架构

### 技术栈

- **后端**：Flask 框架及其扩展（Flask-SQLAlchemy, Flask-Login, Flask-WTF 等）
- **数据库**：SQLite（可扩展到其他数据库）
- **前端**：Bootstrap 4, JavaScript
- **API 集成**：
  - AdGuardHome API
  - 阿里云域名解析 API

### 核心模块

1. **用户认证模块**：处理用户注册、登录和权限管理。

2. **AdGuardHome 服务模块**：与 AdGuardHome API 交互，管理客户端和过滤规则。

3. **域名服务模块**：与阿里云 DNS API 交互，管理域名解析记录。

4. **任务调度模块**：定期检查 IP 变化并更新域名解析。

5. **管理员模块**：系统配置和用户管理。

## 安装与部署

### 环境要求

- Python 3.11 或更高版本
- AdGuardHome 实例（已配置并运行）
- 阿里云账号（用于域名解析）

### 使用 Docker 部署

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/adghm.git
cd adghm
```

2. 创建环境变量文件 `.env`：

```
SECRET_KEY=your_secret_key
ADGUARD_API_BASE_URL=http://your-adguard-home:3000
ADGUARD_USERNAME=your_adguard_username
ADGUARD_PASSWORD=your_adguard_password
```

3. 使用 Docker 构建并运行：

```bash
docker build -t adghm .
docker run -d -p 5000:5000 --name adghm adghm
```

### 手动部署

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/adghm.git
cd adghm
```

2. 创建虚拟环境并安装依赖：

```bash
python -m venv venv
source venv/bin/activate  # 在 Windows 上使用 venv\Scripts\activate
pip install -r requirements.txt
```

3. 创建环境变量文件 `.env`：

```
SECRET_KEY=your_secret_key
ADGUARD_API_BASE_URL=http://your-adguard-home:3000
ADGUARD_USERNAME=your_adguard_username
ADGUARD_PASSWORD=your_adguard_password
```

4. 运行应用：

```bash
python run.py
```

应用将在 http://localhost:5000 上运行。

## 使用指南

### 初始设置

1. **首次访问**：
   - 访问 http://localhost:5000
   - 注册第一个用户账号（将自动成为管理员）

   ![登录页面](/app/static/images/login_page.svg)

2. **系统配置**：
   - 登录管理员账号
   - 访问管理员后台（/admin）
   - 配置 AdGuardHome API 连接信息
   - 配置阿里云域名解析服务信息

### 用户操作

1. **注册和登录**：
   - 用户名必须是 6-12 位数字
   - 登录后可以访问个人主页

2. **客户端管理**：
   - 创建新的 AdGuardHome 客户端
   - 查看和编辑客户端配置
   - 为客户端分配子域名

3. **域名解析**：
   - 系统会自动检测 IP 变化并更新域名解析
   - 用户可以查看自己的域名解析记录

### 管理员操作

1. **用户管理**：
   - 查看所有用户
   - 添加/删除用户
   - 修改用户权限

2. **系统配置**：
   - 更新 AdGuardHome API 配置
   - 更新阿里云域名解析配置
   - 查看系统日志

## 常见问题

1. **域名解析不更新**：
   - 检查阿里云 AccessKey 是否有效
   - 确认域名配置正确
   - 查看任务调度日志

2. **无法连接 AdGuardHome**：
   - 确认 AdGuardHome 实例正在运行
   - 检查 API URL 和认证信息是否正确
   - 确认网络连接正常

3. **客户端创建失败**：
   - 检查 AdGuardHome API 响应
   - 确认客户端 ID 格式正确

## 开发与贡献

### 项目结构

```
adghm/
├── app/                  # 应用主目录
│   ├── __init__.py       # 应用初始化
│   ├── admin/            # 管理员模块
│   ├── auth/             # 认证模块
│   ├── main/             # 主要视图
│   ├── models/           # 数据模型
│   ├── services/         # 服务层
│   ├── static/           # 静态文件
│   ├── templates/        # 模板文件
│   ├── utils/            # 工具函数
│   ├── config.py         # 配置文件
│   └── tasks.py          # 定时任务
├── instance/             # 实例配置和数据
├── openapi/             # API 文档
├── requirements.txt      # 依赖列表
├── run.py               # 应用入口
└── Dockerfile           # Docker 配置
```

### 扩展开发

1. **添加新功能**：
   - 在相应模块中添加新的视图和模板
   - 更新服务层以支持新功能
   - 添加新的数据模型（如需要）

2. **修改现有功能**：
   - 更新相应的视图函数和模板
   - 确保向后兼容性

3. **贡献代码**：
   - Fork 仓库并创建功能分支
   - 提交 Pull Request 并描述变更

## 许可证

本项目采用 MIT 许可证。详情请参阅 LICENSE 文件。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 GitHub Issue

---

感谢使用 AdGuardHome 管理系统！