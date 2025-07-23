from flask_sqlalchemy import SQLAlchemy
from app.utils.timezone import beijing_time

# 避免循环导入，直接从app获取db实例
from app import db


class EmailConfig(db.Model):
    """邮箱配置模型
    
    用于存储和管理邮件服务器的配置信息，包括SMTP服务器设置和认证信息。
    提供配置验证和默认值管理功能。
    """
    __tablename__ = 'email_config'

    id = db.Column(db.Integer, primary_key=True)
    mail_server = db.Column(db.String(255), nullable=False, default='')
    mail_port = db.Column(db.Integer, nullable=False, default=587)
    mail_use_tls = db.Column(db.Boolean, nullable=False, default=True)
    mail_username = db.Column(db.String(255), nullable=False, default='')
    mail_password = db.Column(db.String(255), nullable=False, default='')
    mail_default_sender = db.Column(db.String(255), nullable=False, default='')
    verification_code_expire_minutes = db.Column(db.Integer, nullable=False, default=10)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
    
    def __init__(self, mail_server=None, mail_port=None, mail_use_tls=None, 
                 mail_username=None, mail_password=None, mail_default_sender=None,
                 verification_code_expire_minutes=None):
        """初始化邮箱配置对象
        
        Args:
            mail_server: SMTP服务器地址
            mail_port: SMTP服务器端口
            mail_use_tls: 是否使用TLS加密
            mail_username: SMTP认证用户名
            mail_password: SMTP认证密码
            mail_default_sender: 默认发件人邮箱
            verification_code_expire_minutes: 验证码过期时间（分钟）
        """
        self.mail_server = mail_server or ''
        self.mail_port = mail_port or 587
        self.mail_use_tls = mail_use_tls if mail_use_tls is not None else True
        self.mail_username = mail_username or ''
        self.mail_password = mail_password or ''
        self.mail_default_sender = mail_default_sender or ''
        self.verification_code_expire_minutes = verification_code_expire_minutes or 10
    
    def validate(self):
        """验证配置的有效性
        
        Returns:
            (bool, str): 验证结果和错误信息（如果有）
        """
        if not self.mail_server:
            return False, 'SMTP服务器地址不能为空'
            
        if not self.mail_username:
            return False, 'SMTP用户名不能为空'
            
        if not self.mail_password:
            return False, 'SMTP密码不能为空'
            
        if not self.mail_default_sender:
            return False, '默认发件人邮箱不能为空'
            
        if self.mail_port <= 0 or self.mail_port > 65535:
            return False, 'SMTP端口号必须在1-65535之间'
            
        if self.verification_code_expire_minutes <= 0:
            return False, '验证码过期时间必须大于0分钟'
            
        return True, None

    @classmethod
    def get_config(cls):
        """获取配置，如果不存在则返回空配置
        
        Returns:
            EmailConfig: 配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config
    
    def to_dict(self):
        """转换为字典格式
        
        Returns:
            dict: 配置信息字典
        """
        return {
            'mail_server': self.mail_server,
            'mail_port': self.mail_port,
            'mail_use_tls': self.mail_use_tls,
            'mail_username': self.mail_username,
            'mail_password': self.mail_password,
            'mail_default_sender': self.mail_default_sender,
            'verification_code_expire_minutes': self.verification_code_expire_minutes
        }
    
    def update_from_dict(self, data):
        """从字典更新配置
        
        Args:
            data: 包含配置信息的字典
        """
        if 'mail_server' in data:
            self.mail_server = data['mail_server'].strip()
        if 'mail_port' in data:
            self.mail_port = int(data['mail_port'])
        if 'mail_use_tls' in data:
            self.mail_use_tls = data['mail_use_tls'] in ['true', True, 1, '1']
        if 'mail_username' in data:
            self.mail_username = data['mail_username'].strip()
        if 'mail_password' in data and data['mail_password']:
            # 只有当密码不为空时才更新
            self.mail_password = data['mail_password']
        if 'mail_default_sender' in data:
            self.mail_default_sender = data['mail_default_sender'].strip()
        if 'verification_code_expire_minutes' in data:
            self.verification_code_expire_minutes = int(data['verification_code_expire_minutes'])