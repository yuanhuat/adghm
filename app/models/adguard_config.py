from app import db
from urllib.parse import urlparse
from app.utils.timezone import beijing_time

class AdGuardConfig(db.Model):
    """AdGuardHome配置模型
    
    用于存储和管理AdGuardHome的API配置信息，包括API基础URL和认证信息。
    提供配置验证和默认值管理功能。
    """
    __tablename__ = 'adguard_config'

    id = db.Column(db.Integer, primary_key=True)
    api_base_url = db.Column(db.String(255), nullable=False)
    auth_username = db.Column(db.String(50), nullable=False)
    auth_password = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
    
    # AI分析配置
    deepseek_api_key = db.Column(db.Text)
    auto_analysis_enabled = db.Column(db.Boolean, default=False)
    analysis_threshold = db.Column(db.Float, default=0.8)
    
    def __init__(self, api_base_url=None, auth_username=None, auth_password=None):
        """初始化配置对象
        
        Args:
            api_base_url: AdGuardHome API的基础URL
            auth_username: API认证用户名
            auth_password: API认证密码
        """
        self.api_base_url = api_base_url or ''
        self.auth_username = auth_username or ''
        self.auth_password = auth_password or ''
    
    def validate(self):
        """验证配置的有效性
        
        Returns:
            (bool, str): 验证结果和错误信息（如果有）
        """
        if not self.api_base_url:
            return False, 'API基础URL不能为空'
            
        if not self.auth_username:
            return False, '认证用户名不能为空'
            
        if not self.auth_password:
            return False, '认证密码不能为空'
            
        try:
            # 验证URL格式
            parsed = urlparse(self.api_base_url)
            if not all([parsed.scheme, parsed.netloc]):
                return False, 'API基础URL格式无效'
            
            # 确保URL不以斜杠结尾
            self.api_base_url = self.api_base_url.rstrip('/')
            
            # 验证URL是否包含端口号
            if ':' not in parsed.netloc:
                return False, 'API基础URL必须包含端口号'
            
            # 验证URL是否使用HTTP或HTTPS协议
            if parsed.scheme not in ['http', 'https']:
                return False, 'API基础URL必须使用HTTP或HTTPS协议'
            
            return True, None
            
        except Exception as e:
            return False, f'URL验证失败：{str(e)}'

    @classmethod
    def get_config(cls):
        """获取配置，如果不存在则返回空配置
        
        Returns:
            AdGuardConfig: 配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config