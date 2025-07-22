import os
import sys
import sqlite3
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def migrate_database():
    """添加IPv6相关字段到域名映射表"""
    try:
        # 连接到SQLite数据库
        db_path = os.path.join('instance', 'adghm.db')
        logging.info(f"连接到数据库: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查ipv6_address字段是否已存在
        cursor.execute("PRAGMA table_info(domain_mappings)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 如果字段不存在，则添加
        if 'ipv6_address' not in column_names:
            cursor.execute("ALTER TABLE domain_mappings ADD COLUMN ipv6_address VARCHAR(50)")
            logging.info("成功添加ipv6_address字段到domain_mappings表")
        else:
            logging.info("ipv6_address字段已存在，无需添加")
            
        # 检查ipv6_record_id字段是否已存在
        if 'ipv6_record_id' not in column_names:
            cursor.execute("ALTER TABLE domain_mappings ADD COLUMN ipv6_record_id VARCHAR(50)")
            logging.info("成功添加ipv6_record_id字段到domain_mappings表")
        else:
            logging.info("ipv6_record_id字段已存在，无需添加")
        
        # 提交更改
        conn.commit()
        logging.info("数据库迁移成功完成")
        
    except Exception as e:
        logging.error(f"数据库迁移失败: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database()