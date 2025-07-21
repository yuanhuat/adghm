from datetime import datetime
from app import db

class DomainConfig(db.Model):
    """阿里云域名解析配置模型
    
    用于存储和管理阿里云域名解析的配置信息，包括AccessKey和域名信息。
    提供配置验证和默认值管理功能。
    """
    __tablename__ = 'domain_config'

    id = db.Column(db.Integer, primary_key=True)
    access_key_id = db.Column(db.String(50), nullable=False)
    access_key_secret = db.Column(db.String(255), nullable=False)
    domain_name = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, access_key_id=None, access_key_secret=None, domain_name=None):
        """初始化配置对象
        
        Args:
            access_key_id: 阿里云AccessKey ID
            access_key_secret: 阿里云AccessKey Secret
            domain_name: 主域名
        """
        self.access_key_id = access_key_id or ''
        self.access_key_secret = access_key_secret or ''
        self.domain_name = domain_name or ''
    
    def validate(self):
        """验证配置的有效性
        
        Returns:
            (bool, str): 验证结果和错误信息（如果有）
        """
        if not self.access_key_id:
            return False, 'AccessKey ID不能为空'
            
        if not self.access_key_secret:
            return False, 'AccessKey Secret不能为空'
            
        if not self.domain_name:
            return False, '域名不能为空'
            
        # 验证域名格式
        if '.' not in self.domain_name or self.domain_name.startswith('.'):
            return False, '域名格式无效'
            
        return True, None
        
    def is_valid(self):
        """检查配置是否有效
        
        Returns:
            bool: 配置是否有效
        """
        is_valid, _ = self.validate()
        return is_valid

    @classmethod
    def get_config(cls):
        """获取配置，如果不存在则返回空配置
        
        Returns:
            DomainConfig: 配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config