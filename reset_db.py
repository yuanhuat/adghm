import os
import shutil
from app import create_app

# 创建应用实例
app = create_app()

# 数据库文件路径
db_path = os.path.join(app.root_path, '..', 'instance', 'adghm.db')

# 检查数据库文件是否存在，如果存在则尝试删除
if os.path.exists(db_path):
    print(f"尝试删除现有数据库文件: {db_path}")
    try:
        os.remove(db_path)
        print(f"成功删除数据库文件")
    except PermissionError:
        print(f"无法删除数据库文件，可能正在被其他进程使用")
        print(f"将尝试直接重新创建数据库表")
else:
    print(f"数据库文件不存在: {db_path}")

# 确保instance目录存在
instance_dir = os.path.dirname(db_path)
if not os.path.exists(instance_dir):
    print(f"创建instance目录: {instance_dir}")
    os.makedirs(instance_dir)

# 在应用上下文中重新创建所有数据库表
with app.app_context():
    from app import db
    print("创建新的数据库表...")
    db.create_all()
    print("数据库表创建完成!")

print("数据库重置完成!")