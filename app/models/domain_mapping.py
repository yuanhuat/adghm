from datetime import datetime
from app import db

class DomainMapping(db.Model):
    """用户域名映射模型
    
    用于存储用户与域名之间的关联关系，记录用户的子域名信息。
    """
    __tablename__ = 'domain_mappings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_mapping_id = db.Column(db.Integer, nullable=True)  # 客户端映射ID
    subdomain = db.Column(db.String(50), nullable=False)  # 子域名前缀
    full_domain = db.Column(db.String(255), nullable=False)  # 完整域名
    record_id = db.Column(db.String(50), nullable=False)  # 阿里云解析记录ID
    ip_address = db.Column(db.String(50), nullable=False)  # 解析的IP地址
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联用户
    user = db.relationship('User', backref='domain_mappings')
    
    def __init__(self, user_id, subdomain, full_domain, record_id, ip_address, client_mapping_id=None):
        """初始化域名映射对象
        
        Args:
            user_id: 用户ID
            subdomain: 子域名前缀
            full_domain: 完整域名
            record_id: 阿里云解析记录ID
            ip_address: 解析的IP地址
            client_mapping_id: 客户端映射ID（可选）
        """
        self.user_id = user_id
        self.subdomain = subdomain
        self.full_domain = full_domain
        self.record_id = record_id
        self.ip_address = ip_address
        self.client_mapping_id = client_mapping_id