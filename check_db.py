import os
import sqlite3
from app import create_app

# 创建应用实例
app = create_app()

# 数据库文件路径
db_path = os.path.join(app.root_path, '..', 'instance', 'adghm.db')

print(f"数据库文件路径: {db_path}")

# 检查数据库文件是否存在
if not os.path.exists(db_path):
    print(f"数据库文件不存在: {db_path}")
    exit(1)

# 连接到数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查domain_mappings表结构
cursor.execute("PRAGMA table_info(domain_mappings)")
columns = cursor.fetchall()

print("\ndomain_mappings表结构:")
for column in columns:
    print(f"列名: {column[1]}, 类型: {column[2]}, 是否可为空: {column[3] == 0}, 默认值: {column[4]}")

# 检查domain_mappings表中的数据
cursor.execute("SELECT * FROM domain_mappings LIMIT 5")
rows = cursor.fetchall()

print("\ndomain_mappings表数据示例:")
if rows:
    for row in rows:
        print(row)
else:
    print("表中没有数据")

# 关闭连接
cursor.close()
conn.close()