from flask import current_app, render_template
from flask_mail import Message
from app import mail
from app.models.verification_code import VerificationCode
import threading
from datetime import datetime

class EmailService:
    """邮件服务类"""
    
    @staticmethod
    def send_async_email(app, msg):
        """异步发送邮件
        
        Args:
            app: Flask应用实例
            msg: 邮件消息对象
        """
        with app.app_context():
            try:
                mail.send(msg)
            except Exception as e:
                current_app.logger.error(f'邮件发送失败: {str(e)}')
    
    @classmethod
    def send_email(cls, to, subject, template, config_override=None, **kwargs):
        """发送邮件
        
        Args:
            to: 收件人邮箱
            subject: 邮件主题
            template: 邮件模板名称
            **kwargs: 模板变量
            
        Returns:
            bool: 发送是否成功
        """
        try:
            app = current_app._get_current_object()
            
            if config_override:
                email_config = config_override
            else:
                # 从数据库读取邮箱配置
                from app.models.email_config import EmailConfig
                email_config = EmailConfig.get_config()
            
            # 验证配置
            is_valid, error_msg = email_config.validate()
            if not is_valid:
                current_app.logger.error(f'邮箱配置无效: {error_msg}')
                return False
            
            # 获取系统配置中的项目名称
            from app.models.system_config import SystemConfig
            system_config = SystemConfig.get_config()
            project_name = system_config.project_name if system_config.project_name != '{{ project_name }}' else 'AdGuard Home'
            
            # 动态更新Flask Mail配置
            app.config.update(
                MAIL_SERVER=email_config.mail_server,
                MAIL_PORT=email_config.mail_port,
                MAIL_USE_TLS=email_config.mail_use_tls,
                MAIL_USERNAME=email_config.mail_username,
                MAIL_PASSWORD=email_config.mail_password,
                MAIL_DEFAULT_SENDER=email_config.mail_default_sender
            )
            
            # 重新初始化mail对象以应用新配置
            mail.init_app(app)
            
            msg = Message(
                subject=f'[{project_name}管理系统] {subject}',
                recipients=[to],
                html=render_template(f'email/{template}.html', current_year=datetime.now().year, project_name=project_name, **kwargs),
                sender=email_config.mail_default_sender or email_config.mail_username
            )
            
            # 异步发送邮件
            thr = threading.Thread(target=cls.send_async_email, args=[app, msg])
            thr.start()
            
            return True
        except Exception as e:
            current_app.logger.error(f'邮件发送失败: {str(e)}')
            return False
    
    @classmethod
    def send_verification_code(cls, email, code_type='register'):
        """发送验证码邮件
        
        Args:
            email: 收件人邮箱
            code_type: 验证码类型
            
        Returns:
            tuple: (是否发送成功, 验证码, 错误信息)
        """
        try:
            # 创建验证码
            expire_minutes = current_app.config.get('VERIFICATION_CODE_EXPIRE_MINUTES', 10)
            verification_code = VerificationCode.create_code(
                email=email,
                code_type=code_type,
                expire_minutes=expire_minutes
            )
            
            # 根据验证码类型确定邮件主题和模板
            if code_type == 'register':
                subject = '注册验证码'
                template = 'verification_code'
            elif code_type == 'reset_password':
                subject = '密码重置验证码'
                template = 'reset_password_code'
            elif code_type == 'delete_account':
                subject = '注销账户验证码'
                template = 'delete_account_code'
            elif code_type == 'change_email':
                subject = '修改邮箱验证码'
                template = 'change_email_code'
            elif code_type == 'change_password':
                subject = '修改密码验证码'
                template = 'change_password_code'
            elif code_type.startswith('change_'):
                subject = '账户变更验证码'
                template = 'verification_code'
            else:
                subject = '验证码'
                template = 'verification_code'
            
            # 发送邮件
            success = cls.send_email(
                to=email,
                subject=subject,
                template=template,
                code=verification_code.code,
                expire_minutes=expire_minutes
            )
            
            if success:
                return True, verification_code.code, None
            else:
                return False, None, '邮件发送失败'
                
        except Exception as e:
            current_app.logger.error(f'发送验证码失败: {str(e)}')
            return False, None, str(e)
    
    @classmethod
    def verify_email_code(cls, email, code, code_type='register'):
        """验证邮箱验证码
        
        Args:
            email: 邮箱地址
            code: 验证码
            code_type: 验证码类型
            
        Returns:
            tuple: (是否验证成功, 错误信息)
        """
        return VerificationCode.verify_code(email, code, code_type)