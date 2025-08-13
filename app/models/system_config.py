from app import db
from app.utils.timezone import beijing_time

class SystemConfig(db.Model):
    """系统配置模型
    
    用于存储系统全局设置，如是否允许新用户注册、DNS检测配置等。
    """
    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True)
    allow_registration = db.Column(db.Boolean, default=True, nullable=False, comment='是否允许新用户注册')
    
    # DNS检测配置
    dns_test_domain = db.Column(db.String(255), default='test.dns.con', nullable=False, comment='DNS检测域名')
    dns_test_port = db.Column(db.Integer, default=5000, nullable=False, comment='DNS检测端口')
    dns_test_enabled = db.Column(db.Boolean, default=True, nullable=False, comment='是否启用DNS检测功能')
    
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
    
    def __init__(self, allow_registration=True, dns_test_domain='test.dns.con', dns_test_port=5000, dns_test_enabled=True):
        """初始化系统配置对象
        
        Args:
            allow_registration: 是否允许新用户注册
            dns_test_domain: DNS检测域名
            dns_test_port: DNS检测端口
            dns_test_enabled: 是否启用DNS检测功能
        """
        self.allow_registration = allow_registration
        self.dns_test_domain = dns_test_domain
        self.dns_test_port = dns_test_port
        self.dns_test_enabled = dns_test_enabled
    
    @classmethod
    def get_config(cls):
        """获取系统配置，如果不存在则创建默认配置
        
        Returns:
            SystemConfig: 系统配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config