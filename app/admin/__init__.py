from flask import Blueprint

# 创建管理员蓝图
admin = Blueprint('admin', __name__)

# 导入视图函数
from . import views

from . import views