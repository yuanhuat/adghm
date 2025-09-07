from app import db
from app.utils.timezone import beijing_time

class DnsConfig(db.Model):
    """DNS配置模型
    
    用于存储和管理DNS-over-QUIC和DNS-over-TLS的配置信息，
    供用户在主页查看和使用。
    """
    __tablename__ = 'dns_config'

    id = db.Column(db.Integer, primary_key=True)
    
    # DNS-over-QUIC配置
    doq_enabled = db.Column(db.Boolean, default=True, nullable=False)
    doq_server = db.Column(db.String(255), nullable=True)
    doq_port = db.Column(db.Integer, default=853, nullable=True)
    doq_description = db.Column(db.Text, nullable=True)
    
    # DNS-over-TLS配置
    dot_enabled = db.Column(db.Boolean, default=True, nullable=False)
    dot_server = db.Column(db.String(255), nullable=True)
    dot_port = db.Column(db.Integer, default=853, nullable=True)
    dot_description = db.Column(db.Text, nullable=True)
    
    # DNS-over-HTTPS配置
    doh_enabled = db.Column(db.Boolean, default=True, nullable=False)
    doh_server = db.Column(db.String(255), nullable=True)
    doh_port = db.Column(db.Integer, default=443, nullable=True)
    doh_path = db.Column(db.String(255), default='/dns-query', nullable=True)
    doh_description = db.Column(db.Text, nullable=True)
    
    # 通用配置
    display_title = db.Column(db.String(100), default='DNS配置信息', nullable=False)
    display_description = db.Column(db.Text, nullable=True)
    
    # 苹果设备配置文件下载控制
    apple_config_enabled = db.Column(db.Boolean, default=True, nullable=False)
    apple_doh_config_enabled = db.Column(db.Boolean, default=True, nullable=False)
    apple_dot_config_enabled = db.Column(db.Boolean, default=True, nullable=False)
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=beijing_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time, nullable=False)
    
    def __init__(self):
        """初始化DNS配置对象"""
        self.doq_enabled = True
        self.doq_server = ''
        self.doq_port = 853
        self.doq_description = 'DNS-over-QUIC提供更快的DNS查询速度和更好的隐私保护'
        
        self.dot_enabled = True
        self.dot_server = ''
        self.dot_port = 853
        self.dot_description = 'DNS-over-TLS提供加密的DNS查询，保护您的隐私'
        
        self.doh_enabled = True
        self.doh_server = ''
        self.doh_port = 443
        self.doh_path = '/dns-query'
        self.doh_description = 'DNS-over-HTTPS通过HTTPS协议提供安全的DNS查询'
        
        self.display_title = 'DNS配置信息'
        self.display_description = '以下是{{ project_name }}的DNS配置信息，您可以在设备上配置这些DNS服务器来使用{{ project_name }}的广告拦截和隐私保护功能。'
        
        self.apple_config_enabled = True
        self.apple_doh_config_enabled = True
        self.apple_dot_config_enabled = True
    
    def validate(self):
        """验证配置的有效性
        
        Returns:
            (bool, str): 验证结果和错误信息（如果有）
        """
        errors = []
        
        # 验证DoQ配置
        if self.doq_enabled:
            if not self.doq_server or not self.doq_server.strip():
                errors.append('DNS-over-QUIC服务器地址不能为空')
            if not isinstance(self.doq_port, int) or self.doq_port < 1 or self.doq_port > 65535:
                errors.append('DNS-over-QUIC端口必须是1-65535之间的整数')
        
        # 验证DoT配置
        if self.dot_enabled:
            if not self.dot_server or not self.dot_server.strip():
                errors.append('DNS-over-TLS服务器地址不能为空')
            if not isinstance(self.dot_port, int) or self.dot_port < 1 or self.dot_port > 65535:
                errors.append('DNS-over-TLS端口必须是1-65535之间的整数')
        
        # 验证DoH配置
        if self.doh_enabled:
            if not self.doh_server or not self.doh_server.strip():
                errors.append('DNS-over-HTTPS服务器地址不能为空')
            if not isinstance(self.doh_port, int) or self.doh_port < 1 or self.doh_port > 65535:
                errors.append('DNS-over-HTTPS端口必须是1-65535之间的整数')
            if not self.doh_path or not self.doh_path.strip():
                errors.append('DNS-over-HTTPS路径不能为空')
            elif not self.doh_path.startswith('/'):
                errors.append('DNS-over-HTTPS路径必须以/开头')
        
        # 验证标题
        if not self.display_title or not self.display_title.strip():
            errors.append('显示标题不能为空')
        
        if errors:
            return False, '; '.join(errors)
        
        return True, None
    
    def get_doq_config_string(self):
        """获取DNS-over-QUIC配置字符串
        
        Returns:
            str: DoQ配置字符串，格式为 quic://server:port
        """
        if not self.doq_enabled or not self.doq_server:
            return None
        return f"quic://{self.doq_server.strip()}:{self.doq_port}"
    
    def get_dot_config_string(self):
        """获取DNS-over-TLS配置字符串
        
        Returns:
            str: DoT配置字符串，格式为 tls://server:port
        """
        if not self.dot_enabled or not self.dot_server:
            return None
        return f"tls://{self.dot_server.strip()}:{self.dot_port}"
    
    def get_doh_config_string(self, client_id=None):
        """获取DNS-over-HTTPS配置字符串
        
        Args:
            client_id (str, optional): 客户端ID，如果提供，将添加为子域名前缀
        
        Returns:
            str: DoH配置字符串，格式为 https://client_id.server:port/path 或 https://server:port/path
        """
        if not self.doh_enabled or not self.doh_server:
            return None
        server = self.doh_server.strip()
        path = self.doh_path.strip() if self.doh_path else '/dns-query'
        
        # 如果提供了客户端ID，将其添加为子域名前缀
        if client_id:
            server = f"{client_id}.{server}"
            
        if self.doh_port == 443:
            return f"https://{server}{path}"
        else:
            return f"https://{server}:{self.doh_port}{path}"
    
    @classmethod
    def get_config(cls):
        """获取DNS配置，如果不存在则创建默认配置
        
        Returns:
            DnsConfig: DNS配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config
    
    def to_dict(self):
        """将配置转换为字典格式
        
        Returns:
            dict: 配置字典
        """
        return {
            'id': self.id,
            'doq_enabled': self.doq_enabled,
            'doq_server': self.doq_server,
            'doq_port': self.doq_port,
            'doq_description': self.doq_description,
            'doq_config_string': self.get_doq_config_string(),
            'dot_enabled': self.dot_enabled,
            'dot_server': self.dot_server,
            'dot_port': self.dot_port,
            'dot_description': self.dot_description,
            'dot_config_string': self.get_dot_config_string(),
            'doh_enabled': self.doh_enabled,
            'doh_server': self.doh_server,
            'doh_port': self.doh_port,
            'doh_path': self.doh_path,
            'doh_description': self.doh_description,
            'doh_config_string': self.get_doh_config_string(),  # 不传递client_id，因为to_dict主要用于管理员界面
            'display_title': self.display_title,
            'display_description': self.display_description,
            'apple_config_enabled': self.apple_config_enabled,
            'apple_doh_config_enabled': self.apple_doh_config_enabled,
            'apple_dot_config_enabled': self.apple_dot_config_enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }