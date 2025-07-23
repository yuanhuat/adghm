# AdGuardHome 管理系统安装指南

## 目录

1. [环境准备](#环境准备)
2. [安装方式](#安装方式)
   - [Docker 部署](#docker-部署)
   - [手动部署](#手动部署)
3. [系统配置](#系统配置)
   - [初始化配置](#初始化配置)
   - [AdGuardHome 配置](#adguardhome-配置)
   - [阿里云域名配置](#阿里云域名配置)
4. [升级指南](#升级指南)
5. [故障排除](#故障排除)

## 环境准备

### 系统要求

- **操作系统**：
  - Linux（推荐 Ubuntu 20.04 或更高版本）
  - Windows 10/11 或 Windows Server 2019/2022
  - macOS 11 或更高版本

- **硬件要求**：
  - CPU：双核或更高
  - 内存：至少 2GB RAM
  - 存储：至少 1GB 可用空间

- **软件要求**：
  - Python 3.11 或更高版本
  - pip 包管理器
  - 运行中的 AdGuardHome 实例
  - 阿里云账号（用于域名解析）

### 前置条件

1. **AdGuardHome 安装**：
   - 确保已安装并配置 AdGuardHome
   - 记录 AdGuardHome 管理界面的 URL、用户名和密码

2. **阿里云准备**：
   - 拥有已备案的域名
   - 创建具有 DNS 解析权限的 AccessKey

3. **网络环境**：
   - 确保服务器可以访问互联网
   - 如果在内网部署，确保可以访问 AdGuardHome 实例

## 安装方式

### Docker 部署

Docker 部署是最简单和推荐的安装方式，可以避免环境依赖问题。

#### 前提条件

- 已安装 Docker（版本 20.10 或更高）
- 已安装 Docker Compose（可选，用于多容器部署）

#### 部署步骤

1. **克隆代码仓库**：

```bash
git clone https://github.com/yourusername/adghm.git
cd adghm
```

2. **创建环境变量文件**：

创建 `.env` 文件并填入以下内容：

```
SECRET_KEY=your_random_secret_key
ADGUARD_API_BASE_URL=http://your-adguard-home:3000
ADGUARD_USERNAME=your_adguard_username
ADGUARD_PASSWORD=your_adguard_password
```

> **注意**：请替换上述示例值为您的实际配置。SECRET_KEY 应该是一个随机的长字符串。

3. **构建并启动容器**：

```bash
docker build -t adghm .
docker run -d -p 5000:5000 --name adghm --restart unless-stopped adghm
```

4. **验证部署**：

访问 `http://your-server-ip:5000` 确认系统是否正常运行。

#### 使用 Docker Compose（可选）

1. **创建 docker-compose.yml 文件**：

```yaml
version: '3'

services:
  adghm:
    build: .
    ports:
      - "5000:5000"
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./instance:/app/instance
```

2. **启动服务**：

```bash
docker-compose up -d
```

### 手动部署

如果您希望更灵活地控制部署过程，可以选择手动部署。

#### 前提条件

- Python 3.11 或更高版本
- pip 包管理器
- 虚拟环境工具（推荐）

#### 部署步骤

1. **克隆代码仓库**：

```bash
git clone https://github.com/yourusername/adghm.git
cd adghm
```

2. **创建并激活虚拟环境**：

```bash
# Linux/macOS
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

3. **安装依赖**：

```bash
pip install -r requirements.txt
```

4. **创建环境变量文件**：

创建 `.env` 文件并填入以下内容：

```
SECRET_KEY=your_random_secret_key
ADGUARD_API_BASE_URL=http://your-adguard-home:3000
ADGUARD_USERNAME=your_adguard_username
ADGUARD_PASSWORD=your_adguard_password
```

5. **初始化数据库**：

```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app import db; db.create_all()"
```

6. **启动应用**：

```bash
python run.py
```

7. **验证部署**：

访问 `http://localhost:5000` 确认系统是否正常运行。

#### 生产环境部署

对于生产环境，建议使用 Gunicorn 或 uWSGI 作为 WSGI 服务器，并配合 Nginx 作为反向代理。

1. **安装 Gunicorn**：

```bash
pip install gunicorn
```

2. **创建 Gunicorn 配置文件** `gunicorn_config.py`：

```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "gevent"
timeout = 120
```

3. **使用 Gunicorn 启动应用**：

```bash
gunicorn -c gunicorn_config.py "app:create_app()"
```

4. **配置 Nginx**：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## 系统配置

### 初始化配置

1. **首次访问**：
   - 访问系统 URL（如 `http://your-server-ip:5000`）
   - 注册第一个用户账号（将自动成为管理员）

2. **登录系统**：
   - 使用刚创建的管理员账号登录
   - 进入管理员后台（`/admin`）

### AdGuardHome 配置

1. **配置 AdGuardHome API**：
   - 在管理员后台，导航至「系统配置」>「AdGuardHome 配置」
   - 填写以下信息：
     - API 基础 URL：AdGuardHome 管理界面的 URL（例如：`http://192.168.1.100:3000`）
     - 认证用户名：AdGuardHome 管理员用户名
     - 认证密码：AdGuardHome 管理员密码
   - 点击「保存」按钮
   - 系统会自动测试连接并显示结果

### 阿里云域名配置

1. **创建阿里云 AccessKey**：
   - 登录阿里云控制台
   - 进入「AccessKey 管理」页面
   - 创建 AccessKey（建议使用 RAM 用户创建，并只授予 DNS 解析权限）
   - 记录 AccessKey ID 和 AccessKey Secret

2. **配置域名解析服务**：
   - 在管理员后台，导航至「系统配置」>「域名解析配置」
   - 填写以下信息：
     - AccessKey ID：阿里云 AccessKey ID
     - AccessKey Secret：阿里云 AccessKey Secret
     - 主域名：您拥有的域名（例如：`example.com`）
   - 点击「保存」按钮
   - 系统会自动测试连接并显示结果

## 升级指南

### Docker 部署升级

1. **拉取最新代码**：

```bash
cd adghm
git pull
```

2. **重新构建并启动容器**：

```bash
docker build -t adghm .
docker stop adghm
docker rm adghm
docker run -d -p 5000:5000 --name adghm --restart unless-stopped adghm
```

### 手动部署升级

1. **拉取最新代码**：

```bash
cd adghm
git pull
```

2. **激活虚拟环境**：

```bash
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate    # Windows
```

3. **更新依赖**：

```bash
pip install -r requirements.txt
```

4. **更新数据库**：

```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app import db; db.create_all()"
```

5. **重启应用**：

```bash
# 如果使用 Python 直接运行
python run.py

# 如果使用 Gunicorn
kill -HUP `cat gunicorn.pid`  # 如果有 PID 文件
# 或者重新启动 Gunicorn
gunicorn -c gunicorn_config.py "app:create_app()"
```

## 故障排除

### 常见问题

1. **数据库错误**：
   - 问题：启动时出现数据库相关错误
   - 解决方案：检查数据库文件权限，确保应用有读写权限

2. **无法连接 AdGuardHome API**：
   - 问题：系统无法连接到 AdGuardHome API
   - 解决方案：
     - 确认 AdGuardHome 实例正在运行
     - 检查 API URL 是否正确
     - 验证认证信息
     - 检查网络连接和防火墙设置

3. **域名解析失败**：
   - 问题：无法更新域名解析记录
   - 解决方案：
     - 检查阿里云 AccessKey 权限
     - 确认域名配置正确
     - 查看系统日志中的详细错误信息

### 日志查看

1. **Docker 部署日志**：

```bash
docker logs adghm
```

2. **手动部署日志**：
   - 检查应用输出的控制台日志
   - 如果配置了日志文件，检查相应的日志文件

### 联系支持

如果您遇到无法解决的问题，请通过以下方式获取支持：

- 提交 GitHub Issue
- 发送邮件至：your-email@example.com

---

祝您安装顺利！如有任何问题，请参考项目文档或联系支持团队。