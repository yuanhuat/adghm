# {{ project_name }} 管理系统开发者指南

## 目录

1. [项目架构](#项目架构)
2. [开发环境设置](#开发环境设置)
3. [代码结构](#代码结构)
4. [核心模块](#核心模块)
5. [API 文档](#api-文档)
6. [数据库模型](#数据库模型)
7. [扩展开发](#扩展开发)
8. [测试指南](#测试指南)
9. [贡献指南](#贡献指南)

## 项目架构

### 技术栈概述

{{ project_name }} 管理系统（ADGHM）基于以下技术栈构建：

- **后端框架**：Flask 2.3.x
- **ORM**：SQLAlchemy 2.0.x
- **认证**：Flask-Login
- **表单处理**：Flask-WTF
- **前端框架**：Bootstrap 4
- **数据库**：SQLite（默认，可扩展）
- **任务调度**：Flask-APScheduler
- **API 集成**：
  - {{ project_name }} API
  - 阿里云域名解析 API

### 架构设计

系统采用经典的 MVC（模型-视图-控制器）架构，并增加了服务层以处理复杂的业务逻辑：

1. **模型层（Models）**：定义数据结构和数据库交互
2. **视图层（Views）**：处理 HTTP 请求和响应
3. **模板层（Templates）**：负责 UI 渲染
4. **服务层（Services）**：封装业务逻辑和外部 API 交互
5. **工具层（Utils）**：提供通用功能和辅助方法

## 开发环境设置

### 前提条件

- Python 3.11 或更高版本
- Git
- 文本编辑器或 IDE（推荐 VS Code、PyCharm）
- {{ project_name }} 实例（用于测试）
- 阿里云账号（用于测试域名解析功能）

### 环境设置步骤

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

3. **安装开发依赖**：

```bash
pip install -r requirements.txt
pip install pytest pytest-flask pytest-cov flake8 black
```

4. **创建环境变量文件**：

创建 `.env` 文件并填入以下内容：

```
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=dev_secret_key
ADGUARD_API_BASE_URL=http://your-adguard-home:3000
ADGUARD_USERNAME=your_adguard_username
ADGUARD_PASSWORD=your_adguard_password
```

5. **初始化数据库**：

```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app import db; db.create_all()"
```

6. **启动开发服务器**：

```bash
python run.py
```

## 代码结构

```
adghm/
├── app/                  # 应用主目录
│   ├── __init__.py       # 应用初始化
│   ├── admin/            # 管理员模块
│   │   ├── __init__.py
│   │   └── views.py      # 管理员视图
│   ├── auth/             # 认证模块
│   │   ├── __init__.py
│   │   └── views.py      # 认证视图
│   ├── main/             # 主要视图
│   │   ├── __init__.py
│   │   └── views.py      # 主要视图
│   ├── models/           # 数据模型
│   │   ├── __init__.py
│   │   ├── adguard_config.py
│   │   ├── client_mapping.py
│   │   ├── domain_config.py
│   │   ├── domain_mapping.py
│   │   ├── operation_log.py
│   │   └── user.py
│   ├── services/         # 服务层
│   │   ├── adguard_service.py
│   │   └── domain_service.py
│   ├── static/           # 静态文件
│   │   └── css/
│   ├── templates/        # 模板文件
│   │   ├── admin/
│   │   ├── auth/
│   │   └── main/
│   ├── utils/            # 工具函数
│   │   └── timezone.py
│   ├── config.py         # 配置文件
│   └── tasks.py          # 定时任务
├── docs/                 # 文档
├── instance/             # 实例配置和数据
├── openapi/             # API 文档
├── tests/               # 测试代码
├── .env                 # 环境变量
├── .gitignore
├── Dockerfile
├── requirements.txt     # 依赖列表
├── run.py               # 应用入口
└── README.md
```

## 核心模块

### 认证模块（auth）

认证模块处理用户注册、登录和会话管理。主要文件：

- `app/auth/__init__.py`：定义认证蓝图
- `app/auth/views.py`：实现认证视图函数
- `app/models/user.py`：用户模型定义

关键功能：

- 用户注册和验证
- 用户登录和会话管理
- 密码哈希和验证

### 管理员模块（admin）

管理员模块提供系统配置和用户管理功能。主要文件：

- `app/admin/__init__.py`：定义管理员蓝图
- `app/admin/views.py`：实现管理员视图函数

关键功能：

- 用户管理（创建、编辑、删除）
- 系统配置管理
- 日志查看

### 主要模块（main）

主要模块处理用户的日常操作。主要文件：

- `app/main/__init__.py`：定义主要蓝图
- `app/main/views.py`：实现主要视图函数

关键功能：

- 客户端管理
- 域名映射管理
- 用户主页

### 服务模块（services）

服务模块封装与外部 API 的交互逻辑。主要文件：

- `app/services/adguard_service.py`：{{ project_name }} API 服务
- `app/services/domain_service.py`：阿里云域名解析服务

关键功能：

- {{ project_name }} 客户端管理
- 域名解析记录管理
- IP 地址检测

### 任务模块（tasks）

任务模块处理定时任务和后台作业。主要文件：

- `app/tasks.py`：定义和初始化定时任务

关键功能：

- 自动检测 IP 变化
- 自动更新域名解析记录

## API 文档

系统 API 文档使用 OpenAPI 规范定义，位于 `openapi/` 目录。

### {{ project_name }} API

{{ project_name }} API 的详细文档可在 `openapi/openapi.yaml` 文件中找到。主要端点包括：

- 客户端管理
- 过滤规则配置
- DNS 查询日志

### 内部 API

系统内部 API 主要用于前端与后端的交互，包括：

- 用户认证 API
- 客户端管理 API
- 域名映射 API

## 数据库模型

### 用户模型（User）

```python
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=beijing_time)

    # 关联客户端映射
    client_mappings = db.relationship('ClientMapping', backref='user', lazy=True)
```

### 客户端映射模型（ClientMapping）

```python
class ClientMapping(db.Model):
    __tablename__ = 'client_mappings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    _client_ids = db.Column('client_ids', db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=beijing_time)
```

### 域名映射模型（DomainMapping）

```python
class DomainMapping(db.Model):
    __tablename__ = 'domain_mappings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_mapping_id = db.Column(db.Integer, nullable=True)
    subdomain = db.Column(db.String(50), nullable=False)
    full_domain = db.Column(db.String(255), nullable=False)
    record_id = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    ipv6_address = db.Column(db.String(50), nullable=True)
    ipv6_record_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=beijing_time)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
```

### 配置模型

- `AdGuardConfig`：存储 {{ project_name }} API 配置
- `DomainConfig`：存储阿里云域名解析配置

### 日志模型（OperationLog）

```python
class OperationLog(db.Model):
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    operation_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=beijing_time)
```

## 扩展开发

### 添加新功能

1. **创建新模型**（如需要）：
   - 在 `app/models/` 目录下创建新的模型文件
   - 在 `app/__init__.py` 中导入新模型

2. **创建新服务**（如需要）：
   - 在 `app/services/` 目录下创建新的服务文件
   - 实现服务逻辑

3. **创建新视图**：
   - 在相应的蓝图目录下添加新的视图函数
   - 或创建新的蓝图模块

4. **创建新模板**：
   - 在 `app/templates/` 目录下添加新的模板文件

### 修改现有功能

1. **修改模型**：
   - 更新相应的模型文件
   - 使用数据库迁移工具更新数据库结构

2. **修改服务**：
   - 更新相应的服务文件
   - 确保向后兼容性

3. **修改视图**：
   - 更新相应的视图函数
   - 确保路由和参数处理正确

### 集成新的外部 API

1. **创建新的服务类**：
   - 在 `app/services/` 目录下创建新的服务文件
   - 实现 API 交互逻辑

2. **创建配置模型**：
   - 在 `app/models/` 目录下创建新的配置模型
   - 实现配置验证和管理功能

3. **创建管理界面**：
   - 在管理员模块中添加配置管理视图
   - 创建相应的模板文件

## 测试指南

### 单元测试

项目使用 pytest 进行单元测试。测试文件位于 `tests/` 目录。

1. **运行所有测试**：

```bash
pytest
```

2. **运行特定测试文件**：

```bash
pytest tests/test_auth.py
```

3. **运行带覆盖率报告的测试**：

```bash
pytest --cov=app tests/
```

### 编写测试

1. **测试命名约定**：
   - 测试文件名应以 `test_` 开头
   - 测试函数名应以 `test_` 开头

2. **测试示例**：

```python
# tests/test_auth.py
def test_register(client):
    """测试用户注册功能"""
    response = client.post('/auth/register', data={
        'username': '123456',
        'password': 'password123',
        'confirm_password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'注册成功' in response.data
```

### 测试夹具

项目使用 pytest 夹具来设置测试环境。主要夹具定义在 `tests/conftest.py` 文件中。

```python
# tests/conftest.py
import pytest
from app import create_app, db

@pytest.fixture
def app():
    """创建测试应用实例"""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()
```

## 贡献指南

### 代码风格

项目遵循 PEP 8 代码风格指南，并使用 Black 进行代码格式化。

1. **格式化代码**：

```bash
black app/ tests/
```

2. **检查代码风格**：

```bash
flake8 app/ tests/
```

### 提交规范

1. **分支管理**：
   - `main`：主分支，保持稳定
   - `develop`：开发分支，用于集成功能
   - 功能分支：从 `develop` 分支创建，命名为 `feature/feature-name`
   - 修复分支：从 `main` 分支创建，命名为 `hotfix/issue-number`

2. **提交消息格式**：

```
<类型>(<范围>): <描述>

<详细说明>

<关闭的问题>
```

类型包括：
- `feat`：新功能
- `fix`：错误修复
- `docs`：文档更新
- `style`：代码风格调整
- `refactor`：代码重构
- `test`：测试相关
- `chore`：构建过程或辅助工具变动

示例：

```
feat(auth): 添加用户注册邮箱验证功能

实现了用户注册时的邮箱验证流程，包括：
- 发送验证邮件
- 验证邮箱链接
- 激活账户

Closes #123
```

### Pull Request 流程

1. Fork 仓库并克隆到本地
2. 创建功能分支
3. 实现功能并编写测试
4. 提交代码并推送到 Fork 的仓库
5. 创建 Pull Request 到原仓库的 `develop` 分支
6. 等待代码审查和合并

### 文档贡献

1. **更新文档**：
   - 更新 `docs/` 目录下的文档文件
   - 更新代码注释和文档字符串

2. **API 文档**：
   - 更新 `openapi/` 目录下的 OpenAPI 规范文件

---

感谢您对 {{ project_name }} 管理系统的贡献！如有任何问题，请联系项目维护者。