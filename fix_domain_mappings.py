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

try:
    # 开始事务
    cursor.execute("BEGIN TRANSACTION")
    
    # 创建临时表
    cursor.execute("""
    CREATE TABLE domain_mappings_temp (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        subdomain VARCHAR(50) NOT NULL,
        full_domain VARCHAR(255) NOT NULL,
        record_id VARCHAR(50) NOT NULL,
        ip_address VARCHAR(50) NOT NULL,
        created_at DATETIME,
        updated_at DATETIME,
        client_mapping_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (client_mapping_id) REFERENCES client_mappings (id)
    )
    """)
    
    # 复制数据
    cursor.execute("""
    INSERT INTO domain_mappings_temp 
    SELECT id, user_id, subdomain, full_domain, record_id, ip_address, created_at, updated_at, client_mapping_id 
    FROM domain_mappings
    """)
    
    # 删除旧表
    cursor.execute("DROP TABLE domain_mappings")
    
    # 重命名新表
    cursor.execute("ALTER TABLE domain_mappings_temp RENAME TO domain_mappings")
    
    # 提交事务
    conn.commit()
    print("成功修复 domain_mappings 表结构")
    
    # 检查修复后的表结构
    cursor.execute("PRAGMA table_info(domain_mappings)")
    columns = cursor.fetchall()
    
    print("\n修复后的 domain_mappings 表结构:")
    for column in columns:
        print(f"列名: {column[1]}, 类型: {column[2]}, 是否可为空: {column[3] == 0}, 默认值: {column[4]}")
    
    # 检查外键约束
    cursor.execute("PRAGMA foreign_key_list(domain_mappings)")
    foreign_keys = cursor.fetchall()
    
    print("\n外键约束:")
    for fk in foreign_keys:
        print(f"表: {fk[2]}, 列: {fk[3]}, 引用表: {fk[2]}, 引用列: {fk[4]}")
    
except sqlite3.Error as e:
    # 回滚事务
    conn.rollback()
    print(f"修复表结构时出错: {e}")

# 关闭连接
cursor.close()
conn.close()