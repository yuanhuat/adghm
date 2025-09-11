from app import db
from app.utils.timezone import beijing_time

class SystemConfig(db.Model):
    """系统配置模型
    
    用于存储系统全局设置，如是否允许新用户注册、系统名称等。
    """
    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True)
    allow_registration = db.Column(db.Boolean, default=True, nullable=False, comment='是否允许新用户注册')
    project_name = db.Column(db.String(100), default='AdGuard Home Manager', nullable=False, comment='系统名称')
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
    
    def __init__(self, allow_registration=True, project_name='AdGuard Home Manager'):
        """初始化系统配置对象
        
        Args:
            allow_registration: 是否允许新用户注册
            project_name: 系统名称
        """
        self.allow_registration = allow_registration
        self.project_name = project_name
    
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