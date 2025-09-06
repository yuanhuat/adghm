from app import db
from app.utils.timezone import beijing_time

class OpenListConfig(db.Model):
    """OpenList配置模型
    
    用于存储OpenList对接的相关配置参数，包括服务器地址、认证信息等。
    """
    __tablename__ = 'openlist_config'

    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False, comment='是否启用OpenList对接')
    server_url = db.Column(db.String(255), default='', nullable=False, comment='OpenList服务器地址')
    username = db.Column(db.String(100), default='', nullable=False, comment='OpenList用户名')
    password = db.Column(db.String(255), default='', nullable=False, comment='OpenList密码')
    token = db.Column(db.Text, default='', nullable=False, comment='OpenList访问令牌')
    token_expires_at = db.Column(db.DateTime, nullable=True, comment='令牌过期时间')
    sync_interval = db.Column(db.Integer, default=3600, nullable=False, comment='同步间隔(秒)')
    auto_sync = db.Column(db.Boolean, default=False, nullable=False, comment='是否自动同步')
    last_sync_at = db.Column(db.DateTime, nullable=True, comment='最后同步时间')
    sync_status = db.Column(db.String(50), default='未同步', nullable=False, comment='同步状态')
    description = db.Column(db.Text, default='', nullable=False, comment='配置描述')
    created_at = db.Column(db.DateTime, default=beijing_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
    
    def __init__(self, enabled=False, server_url='', username='', password='', 
                 sync_interval=3600, auto_sync=False, description=''):
        """初始化OpenList配置对象
        
        Args:
            enabled: 是否启用OpenList对接
            server_url: OpenList服务器地址
            username: OpenList用户名
            password: OpenList密码
            sync_interval: 同步间隔(秒)
            auto_sync: 是否自动同步
            description: 配置描述
        """
        self.enabled = enabled
        self.server_url = server_url
        self.username = username
        self.password = password
        self.sync_interval = sync_interval
        self.auto_sync = auto_sync
        self.description = description
    
    @classmethod
    def get_config(cls):
        """获取OpenList配置，如果不存在则创建默认配置
        
        Returns:
            OpenListConfig: OpenList配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config
    
    def to_dict(self):
        """将配置对象转换为字典
        
        Returns:
            dict: 配置字典
        """
        return {
            'id': self.id,
            'enabled': self.enabled,
            'server_url': self.server_url,
            'username': self.username,
            'password': '***' if self.password else '',  # 密码脱敏
            'token': '***' if self.token else '',  # 令牌脱敏
            'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
            'sync_interval': self.sync_interval,
            'auto_sync': self.auto_sync,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'sync_status': self.sync_status,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_token_valid(self):
        """检查令牌是否有效
        
        Returns:
            bool: 令牌是否有效
        """
        if not self.token or not self.token_expires_at:
            return False
        return self.token_expires_at > beijing_time()
    
    def __repr__(self):
        return f'<OpenListConfig {self.id}: {self.server_url}>'