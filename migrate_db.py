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

# 检查domain_mappings表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='domain_mappings'")
table_exists = cursor.fetchone()

if not table_exists:
    print("domain_mappings表不存在，无法迁移")
    conn.close()
    exit(1)

# 检查client_mapping_id列是否存在
cursor.execute("PRAGMA table_info(domain_mappings)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

if 'client_mapping_id' in column_names:
    print("client_mapping_id列已存在，无需迁移")
else:
    print("添加client_mapping_id列到domain_mappings表")
    try:
        # 添加client_mapping_id列
        cursor.execute("ALTER TABLE domain_mappings ADD COLUMN client_mapping_id INTEGER")
        conn.commit()
        print("成功添加client_mapping_id列")
    except sqlite3.Error as e:
        print(f"添加列时出错: {e}")
        conn.rollback()

# 关闭连接
conn.close()

print("数据库迁移完成!")