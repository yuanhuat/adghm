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
            
            # 处理IPv4地址更新
            if 'ipv4' in ip_addresses:
                ipv4_address = ip_addresses['ipv4']
                for mapping in domain_mappings:
                    # 检查IP地址是否变化
                    if mapping.ip_address == ipv4_address:
                        logging.debug(f'域名映射 {mapping.full_domain} 的IPv4地址未变化，无需更新')
                        continue
                          
                    try:
                        # 更新阿里云域名解析记录
                        domain_service.update_domain_record(
                            mapping.record_id,
                            mapping.subdomain,
                            ipv4_address
                        )
                        
                        # 记录操作日志
                        log = OperationLog(
                            user_id=mapping.user_id,
                            operation_type='auto_update_ip',
                            target_type='domain_mapping',
                            target_id=str(mapping.id),
                            details=f'自动更新域名映射IPv4地址：{mapping.full_domain}，从 {mapping.ip_address} 更新为 {ipv4_address}'
                        )
                        db.session.add(log)
                        
                        # 更新映射记录
                        mapping.ip_address = ipv4_address
                        updated_count += 1
                        logging.info(f'成功更新域名映射 {mapping.full_domain} 的IPv4地址为 {ipv4_address}')
                          
                    except Exception as e:
                        logging.error(f'自动更新域名映射 {mapping.full_domain} 的IPv4地址失败: {str(e)}')
            
            # 处理IPv6地址更新
            if 'ipv6' in ip_addresses:
                ipv6_address = ip_addresses['ipv6']
                ipv6_updated_count = 0
                
                for mapping in domain_mappings:
                    # 检查IPv6地址是否变化
                    if mapping.ipv6_address == ipv6_address:
                        logging.debug(f'域名映射 {mapping.full_domain} 的IPv6地址未变化，无需更新')
                        continue
                    
                    try:
                        # 如果已有IPv6记录ID，则更新记录
                        if mapping.ipv6_record_id:
                            domain_service.update_domain_record(
                                mapping.ipv6_record_id,
                                mapping.subdomain,
                                ipv6_address
                            )
                            
                            # 记录操作日志
                            log = OperationLog(
                                user_id=mapping.user_id,
                                operation_type='auto_update_ip',
                                target_type='domain_mapping',
                                target_id=str(mapping.id),
                                details=f'自动更新域名映射IPv6地址：{mapping.full_domain}，从 {mapping.ipv6_address or "无"} 更新为 {ipv6_address}'
                            )
                            db.session.add(log)
                            
                            # 更新映射记录
                            mapping.ipv6_address = ipv6_address
                            ipv6_updated_count += 1
                            logging.info(f'成功更新域名映射 {mapping.full_domain} 的IPv6地址为 {ipv6_address}')
                        
                        # 如果没有IPv6记录ID，则创建新记录
                        else:
                            # 创建AAAA记录
                            request = AddDomainRecordRequest()
                            request.set_accept_format('json')
                            request.set_DomainName(domain_config.domain_name)
                            request.set_RR(mapping.subdomain)  # 子域名前缀
                            request.set_Type("AAAA")  # AAAA记录(IPv6)
                            request.set_Value(ipv6_address)  # 解析到的IPv6地址
                            request.set_TTL(600)  # 生存时间，单位秒
                            
                            # 发送请求
                            response = domain_service.client.do_action_with_exception(request)
                            result = json.loads(response.decode('utf-8'))
                            
                            # 获取记录ID并保存
                            ipv6_record_id = result.get('RecordId', '')
                            if ipv6_record_id:
                                # 记录操作日志
                                log = OperationLog(
                                    user_id=mapping.user_id,
                                    operation_type='create_ipv6_record',
                                    target_type='domain_mapping',
                                    target_id=str(mapping.id),
                                    details=f'创建域名映射IPv6记录：{mapping.full_domain} -> {ipv6_address}'
                                )
                                db.session.add(log)
                                
                                # 更新映射记录
                                mapping.ipv6_address = ipv6_address
                                mapping.ipv6_record_id = ipv6_record_id
                                ipv6_updated_count += 1
                                logging.info(f'成功创建域名映射 {mapping.full_domain} 的IPv6记录，地址为 {ipv6_address}')
                    
                    except Exception as e:
                        logging.error(f'自动更新域名映射 {mapping.full_domain} 的IPv6地址失败: {str(e)}')
                
                updated_count += ipv6_updated_count
            
            if updated_count > 0:
                db.session.commit()
                logging.info(f'自动更新IP地址成功，共更新了 {updated_count} 条域名映射记录')
            else:
                logging.info('所有域名映射的IP地址均未变化，无需更新')
                  
        except Exception as e:
            db.session.rollback()
            logging.error(f'自动更新IP地址失败: {str(e)}')