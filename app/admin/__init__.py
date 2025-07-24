from flask import Blueprint

admin = Blueprint('admin', __name__)

# 导入视图
from . import views