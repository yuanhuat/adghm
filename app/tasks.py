import logging
import sys
import json
from flask import current_app
from app import scheduler, db

from app.models.operation_log import OperationLog


# 全局变量，用于存储Flask应用实例
flask_app = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def init_scheduler_tasks(app):
    """初始化调度器任务"""
    # 保存应用实例供定时任务使用
    global flask_app
    flask_app = app
    
    with app.app_context():
        # 在这里可以添加其他定时任务
        pass