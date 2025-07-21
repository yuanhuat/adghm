from flask import Blueprint

# 创建主蓝图
main = Blueprint('main', __name__)

# 导入视图函数
from . import views