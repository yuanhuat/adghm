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