from flask import Blueprint

# 创建认证蓝图
auth = Blueprint('auth', __name__)

# 导入视图函数，放在最后以避免循环导入
from . import views