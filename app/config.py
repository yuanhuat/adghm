import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.dirname(basedir)
load_dotenv(os.path.join(project_root, '.env'))

class Config:
    """应用配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(project_root, 'instance', 'adghm.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AdGuardHome API配置
    ADGUARD_API_BASE_URL = os.environ.get('ADGUARD_API_BASE_URL')
    ADGUARD_USERNAME = os.environ.get('ADGUARD_USERNAME')
    ADGUARD_PASSWORD = os.environ.get('ADGUARD_PASSWORD')
    
    # 邮件配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.qq.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # 验证码配置
    VERIFICATION_CODE_EXPIRE_MINUTES = int(os.environ.get('VERIFICATION_CODE_EXPIRE_MINUTES') or 10)