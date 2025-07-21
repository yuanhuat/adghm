import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from app.config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # 确保实例文件夹存在
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)
    login_manager.init_app(app)

    # 注册蓝图
    from app.auth import auth
    from app.admin import admin
    from app.main import main

    app.register_blueprint(auth)
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(main)

    # 导入所有模型以确保它们在创建数据库表之前被定义
    from app.models import User, ClientMapping, OperationLog, AdGuardConfig

    # 在应用上下文中创建所有数据库表
    with app.app_context():
        db.create_all()

    return app