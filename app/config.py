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

    # 分页配置
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE') or 20)
    
    # 支付配置
    PAYMENT_TIMEOUT = int(os.environ.get('PAYMENT_TIMEOUT') or 300)  # 支付超时时间（秒）
    PAYMENT_MIN_AMOUNT = float(os.environ.get('PAYMENT_MIN_AMOUNT') or 0.01)  # 最小支付金额
    PAYMENT_MAX_AMOUNT = float(os.environ.get('PAYMENT_MAX_AMOUNT') or 10000)  # 最大支付金额
    PAYMENT_CURRENCY = os.environ.get('PAYMENT_CURRENCY') or 'CNY'  # 支付货币
    PAYMENT_NOTIFY_URL = os.environ.get('PAYMENT_NOTIFY_URL')  # 支付异步通知地址
    PAYMENT_RETURN_URL = os.environ.get('PAYMENT_RETURN_URL')  # 支付同步返回地址