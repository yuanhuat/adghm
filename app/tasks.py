import logging
import sys
import json
from flask import current_app
from app import scheduler, db
from app.models.domain_mapping import DomainMapping
from app.models.domain_config import DomainConfig
from app.services.domain_service import DomainService
from app.models.operation_log import OperationLog
from aliyunsdkalidns.request.v20150109.AddDomainRecordRequest import AddDomainRecordRequest

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
        # 检查任务是否已存在，避免重复添加
        if not scheduler.get_job('auto_update_ip'):
            # 添加自动更新IP地址的定时任务，每60秒执行一次
            scheduler.add_job(
                id='auto_update_ip',
                func=auto_update_ip,
                trigger='interval',
                seconds=60,
                replace_existing=True
            )
            logging.info('已添加自动更新IP地址的定时任务')
        else:
            logging.info('自动更新IP地址的定时任务已存在，跳过添加')

def auto_update_ip():
    """自动更新所有用户的域名解析IP地址，同时支持IPv4和IPv6"""
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
            
            # 获取最新IP地址（同时获取IPv4和IPv6）
            ip_addresses = domain_service.get_current_ip('both')
            
            if not ip_addresses or not isinstance(ip_addresses, dict):
                logging.error('无法获取当前IP地址，自动更新IP地址失败')
                return
            
            logging.info(f'获取到IP地址: {ip_addresses}')
              
            # 获取所有域名映射
            domain_mappings = DomainMapping.query.all()
            
            if not domain_mappings:
                logging.info('没有域名映射记录，无需更新IP地址')
                return
              
            updated_count = 0
            
            for mapping in domain_mappings:
                ipv4_address = ip_addresses.get('ipv4')
                ipv6_address = ip_addresses.get('ipv6')

                # 检查IPv4和IPv6地址是否都未变化
                ipv4_changed = ipv4_address and mapping.ip_address != ipv4_address
                ipv6_changed = ipv6_address and mapping.ipv6_address != ipv6_address

                if not ipv4_changed and not ipv6_changed:
                    logging.debug(f'域名映射 {mapping.full_domain} 的IP地址未变化，无需更新')
                    continue

                try:
                    details_parts = []
                    # 更新IPv4地址
                    if ipv4_changed:
                        domain_service.update_domain_record(
                            mapping.record_id,
                            mapping.subdomain,
                            ipv4_address
                        )
                        details_parts.append(f'IPv4从 {mapping.ip_address} 更新为 {ipv4_address}')
                        mapping.ip_address = ipv4_address
                        logging.info(f'成功更新域名映射 {mapping.full_domain} 的IPv4地址为 {ipv4_address}')

                    # 更新IPv6地址
                    if ipv6_changed:
                        if mapping.ipv6_record_id:
                            # 更新现有的IPv6记录
                            domain_service.update_domain_record(
                                mapping.ipv6_record_id,
                                mapping.subdomain,
                                ipv6_address
                            )
                            details_parts.append(f'IPv6从 {mapping.ipv6_address or "无"} 更新为 {ipv6_address}')
                            mapping.ipv6_address = ipv6_address
                            logging.info(f'成功更新域名映射 {mapping.full_domain} 的IPv6地址为 {ipv6_address}')
                        else:
                            # 创建新的IPv6记录
                            try:
                                result = domain_service.add_ipv6_record(mapping.subdomain, ipv6_address)
                                ipv6_record_id = result.get('RecordId', '')
                                if ipv6_record_id:
                                    details_parts.append(f'IPv6创建为 {ipv6_address}')
                                    mapping.ipv6_address = ipv6_address
                                    mapping.ipv6_record_id = ipv6_record_id
                                    logging.info(f'成功创建域名映射 {mapping.full_domain} 的IPv6记录，地址为 {ipv6_address}')
                                else:
                                    logging.warning(f'创建IPv6记录失败，未获取到记录ID: {mapping.full_domain}')
                            except Exception as ipv6_error:
                                logging.error(f'创建IPv6记录失败: {mapping.full_domain}, 错误: {str(ipv6_error)}')

                    # 记录统一的操作日志
                    log = OperationLog(
                        user_id=mapping.user_id,
                        operation_type='auto_update_ip',
                        target_type='domain_mapping',
                        target_id=str(mapping.id),
                        details=f'自动更新域名映射IP地址：{mapping.full_domain}，' + '；'.join(details_parts)
                    )
                    db.session.add(log)
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