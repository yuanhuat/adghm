import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from app.config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
mail = Mail()
scheduler = APScheduler()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # 确保实例文件夹存在
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    # 注册蓝图
    from app.auth import auth
    from app.admin import admin
    from app.main import main

    app.register_blueprint(auth)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(main)

    # 导入所有模型以确保它们在创建数据库表之前被定义
    from app.models import User, ClientMapping, OperationLog, AdGuardConfig, Feedback, VerificationCode, EmailConfig, DonationConfig
    from app.models.query_log_analysis import QueryLogAnalysis, QueryLogExport

    # 在应用上下文中创建所有数据库表
    with app.app_context():
        db.create_all()
    
    # 添加全局模板上下文处理器
    @app.context_processor
    def inject_global_vars():
        """注入全局模板变量
        
        Returns:
            dict: 包含全局变量的字典
        """
        from app.models import SystemConfig
        config = SystemConfig.get_config() if hasattr(SystemConfig, 'get_config') else None
        return {
            'project_name': config.project_name if config and hasattr(config, 'project_name') else 'AdGuard Home Manager'
        }
    
    # 初始化调度器
    scheduler.init_app(app)
    scheduler.start()
    
    # 添加自动更新IP地址的定时任务
    from app.tasks import init_scheduler_tasks
    init_scheduler_tasks(app)

    return app