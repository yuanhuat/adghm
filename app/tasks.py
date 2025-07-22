import logging
import sys
from flask import current_app
from app import scheduler, db
from app.models.domain_mapping import DomainMapping
from app.models.domain_config import DomainConfig
from app.services.domain_service import DomainService
from app.models.operation_log import OperationLog

# 全局变量，用于存储Flask应用实例
flask_app = None

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def init_scheduler_tasks(app):
    """初始化调度器任务"""
    # 保存应用实例供定时任务使用
    global flask_app
    flask_app = app
    
    with app.app_context():
        # 添加自动更新IP地址的定时任务，每60秒执行一次
        scheduler.add_job(
            id='auto_update_ip',
            func=auto_update_ip,
            trigger='interval',
            seconds=60,
            replace_existing=True
        )
        logging.info('已添加自动更新IP地址的定时任务')

def auto_update_ip():
    """自动更新所有用户的域名解析IP地址"""
    # 使用全局应用实例创建应用上下文
    global flask_app
    
    if not flask_app:
        logging.error('找不到Flask应用实例，无法执行自动更新IP地址任务')
        return
    
    # 在应用上下文中执行所有操作
    with flask_app.app_context():
        try:
            # 获取域名配置
            domain_config = DomainConfig.query.first()
            if not domain_config or not domain_config.is_valid():
                logging.error('域名服务未配置或配置无效，无法自动更新IP地址')
                return
                  
            # 创建域名服务实例
            domain_service = DomainService(domain_config)
            
            # 获取最新IP地址
            ip_address = domain_service.get_current_ip()
            
            if not ip_address:
                logging.error('无法获取当前IP地址，自动更新IP地址失败')
                return
              
            # 获取所有域名映射
            domain_mappings = DomainMapping.query.all()
            
            if not domain_mappings:
                logging.info('没有域名映射记录，无需更新IP地址')
                return
              
            updated_count = 0
            for mapping in domain_mappings:
                # 检查IP地址是否变化
                if mapping.ip_address == ip_address:
                    continue
                      
                try:
                    # 更新阿里云域名解析记录
                    domain_service.update_domain_record(
                        mapping.record_id,
                        mapping.subdomain,
                        ip_address
                    )
                    
                    # 记录操作日志
                    log = OperationLog(
                        user_id=mapping.user_id,
                        operation_type='auto_update_ip',
                        target_type='domain_mapping',
                        target_id=str(mapping.id),
                        details=f'自动更新域名映射IP地址：{mapping.full_domain}，从 {mapping.ip_address} 更新为 {ip_address}'
                    )
                    db.session.add(log)
                    
                    # 更新映射记录
                    mapping.ip_address = ip_address
                    updated_count += 1
                      
                except Exception as e:
                    logging.error(f'自动更新域名映射 {mapping.full_domain} 的IP地址失败: {str(e)}')
            
            if updated_count > 0:
                db.session.commit()
                logging.info(f'自动更新IP地址成功，共更新了 {updated_count} 条域名映射记录')
            else:
                logging.info('所有域名映射的IP地址均未变化，无需更新')
                  
        except Exception as e:
            db.session.rollback()
            logging.error(f'自动更新IP地址失败: {str(e)}')