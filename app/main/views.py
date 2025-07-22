import logging
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog
from app.models.domain_mapping import DomainMapping
from app.models.domain_config import DomainConfig
from app.services.adguard_service import AdGuardService
from app.services.domain_service import DomainService
from app.admin.views import admin_required
from . import main



@main.route('/')
@login_required
def index():
    """用户主页
    
    显示用户的客户端列表和基本信息，以及域名映射信息
    """
    # 获取用户的域名映射信息
    domain_mapping = DomainMapping.query.filter_by(user_id=current_user.id).first()
    return render_template('main/index.html', domain_mapping=domain_mapping)

@main.route('/domain-info')
@login_required
def domain_info():
    """获取用户的域名信息"""
    client_id = request.args.get('client_id')
    
    if client_id:
        # 检查客户端是否属于当前用户
        client_mapping = ClientMapping.query.filter_by(id=client_id, user_id=current_user.id).first()
        if not client_mapping:
            return jsonify({
                'success': False,
                'error': '客户端不存在或无权访问'
            })
            
        # 使用客户端ID作为子域名前缀
        subdomain = client_mapping.client_ids[0]
        
        # 获取与客户端关联的域名映射
        domain_mapping = DomainMapping.query.filter_by(client_mapping_id=client_id).first()
    else:
        # 获取用户的任意域名映射（用于主页显示）
        domain_mapping = DomainMapping.query.join(ClientMapping).filter(ClientMapping.user_id==current_user.id).first()
    
    if domain_mapping:
        return jsonify({
            'success': True,
            'domain_mapping': {
                'subdomain': domain_mapping.subdomain,
                'full_domain': domain_mapping.full_domain,
                'created_at': domain_mapping.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    else:
        return jsonify({
            'success': True,
            'domain_mapping': None
        })

@main.route('/domain-mapping', methods=['POST', 'DELETE'])
@login_required
def manage_domain_mapping():
    """创建、更新或删除域名映射"""
    if request.method == 'POST':
        data = request.get_json()
        client_id = data.get('client_id')
        
        if not client_id:
            return jsonify({
                'success': False,
                'error': '缺少必要参数'
            })
        
        # 检查客户端是否属于当前用户
        client_mapping = ClientMapping.query.filter_by(id=client_id, user_id=current_user.id).first()
        if not client_mapping:
            return jsonify({
                'success': False,
                'error': '客户端不存在或无权访问'
            })
        
        # 获取域名配置
        domain_config = DomainConfig.query.first()
        if not domain_config or not domain_config.is_valid():
            return jsonify({
                'success': False,
                'error': '域名服务未配置或配置无效'
            })
        
        # 创建域名服务实例
        domain_service = DomainService(domain_config)
        
        try:
            # 获取当前IP地址
            ip_address = domain_service.get_current_ip()
            
            # 检查是否已存在域名映射
            domain_mapping = DomainMapping.query.filter_by(client_mapping_id=client_id).first()
            
            if domain_mapping:
                # 更新现有域名映射
                old_subdomain = domain_mapping.subdomain
                
                # 如果子域名发生变化，需要删除旧记录并创建新记录
                if old_subdomain != subdomain:
                    try:
                        # 删除旧的解析记录
                        domain_service.delete_domain_record(domain_mapping.record_id)
                    except Exception as e:
                        logging.error(f'删除旧域名记录失败: {str(e)}')
                    
                    # 创建新的解析记录
                    record_id = domain_service.add_domain_record(subdomain, ip_address)
                    domain_mapping.record_id = record_id
                    domain_mapping.subdomain = subdomain
                    domain_mapping.full_domain = f'{subdomain}.{domain_config.domain_name}'
                else:
                    # 子域名未变，只更新IP地址
                    domain_service.update_domain_record(domain_mapping.record_id, subdomain, ip_address)
                
                domain_mapping.ip_address = ip_address
                message = '域名映射更新成功'
            else:
                # 创建新的域名映射
                record_id = domain_service.add_domain_record(subdomain, ip_address)
                domain_mapping = DomainMapping(
                    user_id=current_user.id,
                    client_mapping_id=client_id,
                    subdomain=subdomain,
                    full_domain=f'{subdomain}.{domain_config.domain_name}',
                    record_id=record_id,
                    ip_address=ip_address
                )
                db.session.add(domain_mapping)
                message = '域名映射创建成功'
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_domain_mapping',
                target_type='domain_mapping',
                target_id=str(domain_mapping.id),
                details=f'{message}: {domain_mapping.full_domain}, IP: {ip_address}'
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': message,
                'domain_mapping': {
                    'subdomain': domain_mapping.subdomain,
                    'full_domain': domain_mapping.full_domain,
                    'created_at': domain_mapping.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f'配置域名映射失败: {str(e)}')
            return jsonify({
                'success': False,
                'error': f'配置域名映射失败: {str(e)}'
            })
    
    elif request.method == 'DELETE':
        data = request.get_json()
        client_id = data.get('client_id')
        
        if not client_id:
            return jsonify({
                'success': False,
                'error': '缺少客户端ID'
            })
        
        # 检查客户端是否属于当前用户
        client_mapping = ClientMapping.query.filter_by(id=client_id, user_id=current_user.id).first()
        if not client_mapping:
            return jsonify({
                'success': False,
                'error': '客户端不存在或无权访问'
            })
        
        # 查找域名映射
        domain_mapping = DomainMapping.query.filter_by(client_mapping_id=client_id).first()
        if not domain_mapping:
            return jsonify({
                'success': False,
                'error': '域名映射不存在'
            })
        
        try:
            # 获取域名配置
            domain_config = DomainConfig.query.first()
            if domain_config and domain_config.is_valid():
                # 创建域名服务实例
                domain_service = DomainService(domain_config)
                
                # 删除阿里云解析记录
                try:
                    domain_service.delete_domain_record(domain_mapping.record_id)
                except Exception as e:
                    logging.error(f'删除阿里云解析记录失败: {str(e)}')
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='delete_domain_mapping',
                target_type='domain_mapping',
                target_id=str(domain_mapping.id),
                details=f'删除域名映射: {domain_mapping.full_domain}'
            )
            db.session.add(log)
            
            # 删除数据库中的域名映射
            db.session.delete(domain_mapping)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '域名映射删除成功'
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f'删除域名映射失败: {str(e)}')
            return jsonify({
                'success': False,
                'error': f'删除域名映射失败: {str(e)}'
            })



@main.route('/clients')
@login_required
def clients():
    """客户端管理页面
    
    显示用户的所有客户端及其详细信息
    """
    return render_template('main/clients.html')

@main.route('/api/blocked_services')
@login_required
def get_blocked_services():
    """获取可用的阻止服务列表
    
    从AdGuardHome API获取所有可用的阻止服务列表
    
    Returns:
        JSON响应，包含可用的阻止服务列表
    """
    try:
        # 从AdGuardHome API获取可用的阻止服务列表
        adguard = AdGuardService()
        response = adguard.get_blocked_services_all()
        
        # 提取服务信息，只保留id和name字段
        services = []
        if response and isinstance(response, dict) and 'blocked_services' in response:
            for service in response['blocked_services']:
                services.append({
                    "id": service.get('id', ''),
                    "name": service.get('name', '')
                })
        
        # 如果API返回为空，使用备用静态列表
        if not services:
            logging.warning("从AdGuardHome API获取阻止服务列表为空，使用备用列表")
            services = [
                {"id": "facebook", "name": "Facebook"},
                {"id": "twitter", "name": "Twitter"},
                {"id": "youtube", "name": "YouTube"},
                {"id": "instagram", "name": "Instagram"},
                {"id": "netflix", "name": "Netflix"},
                {"id": "whatsapp", "name": "WhatsApp"},
                {"id": "tiktok", "name": "TikTok"},
                {"id": "twitch", "name": "Twitch"},
                {"id": "discord", "name": "Discord"},
                {"id": "reddit", "name": "Reddit"},
                {"id": "snapchat", "name": "Snapchat"},
                {"id": "pinterest", "name": "Pinterest"},
                {"id": "skype", "name": "Skype"},
                {"id": "amazon", "name": "Amazon"},
                {"id": "ebay", "name": "eBay"},
                {"id": "gmail", "name": "Gmail"},
                {"id": "origin", "name": "Origin"},
                {"id": "steam", "name": "Steam"},
                {"id": "epic_games", "name": "Epic Games"},
                {"id": "wechat", "name": "WeChat"},
                {"id": "qq", "name": "QQ"},
                {"id": "baidu", "name": "Baidu"}
            ]
        
        # 按名称排序
        services.sort(key=lambda x: x.get('name', ''))
        
        return jsonify({
            "success": True,
            "services": services
        })
    except Exception as e:
        logging.error(f"获取阻止服务列表失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"获取阻止服务列表失败：{str(e)}"
        }), 500


@main.route('/api/global_blocked_services', methods=['GET', 'PUT'])
@login_required
@admin_required
def global_blocked_services():
    """获取或更新全局阻止服务设置
    
    GET: 获取当前的全局阻止服务设置
    PUT: 更新全局阻止服务设置
    
    Returns:
        JSON响应，包含操作结果
    """
    adguard = AdGuardService()
    
    if request.method == 'GET':
        try:
            # 获取当前的阻止服务配置
            response = adguard.get_blocked_services()
            
            return jsonify({
                "success": True,
                "blocked_services": response.get('ids', []),
                "schedule": response.get('schedule', {})
            })
        except Exception as e:
            logging.error(f"获取全局阻止服务设置失败: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"获取全局阻止服务设置失败：{str(e)}"
            }), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "无效的请求数据"}), 400
            
            # 提取请求数据
            blocked_services = data.get('ids', [])
            schedule = data.get('schedule', None)
            
            # 更新阻止服务配置
            response = adguard.update_blocked_services(schedule=schedule, ids=blocked_services)
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_global_blocked_services',
                target_type='GLOBAL_SETTING',
                target_id='blocked_services',
                details=f"更新全局阻止服务设置，阻止的服务数量：{len(blocked_services)}"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "全局阻止服务设置已更新"
            })
        except Exception as e:
            logging.error(f"更新全局阻止服务设置失败: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"更新全局阻止服务设置失败：{str(e)}"
            }), 500

@main.route('/clients/<int:mapping_id>', methods=['GET', 'PUT'])
@login_required
def client_details(mapping_id):
    """获取或更新客户端配置
    
    Args:
        mapping_id: 客户端映射ID
    """
    mapping = ClientMapping.query.get_or_404(mapping_id)
    
    # 验证权限
    if mapping.user_id != current_user.id:
        return jsonify({'error': '没有权限操作此客户端'}), 403
    
    if request.method == 'GET':
        try:
            # 获取AdGuardHome客户端信息
            adguard = AdGuardService()
            client_info = adguard.find_client(mapping.client_name)
            
            if not client_info:
                return jsonify({
                    'client_ids': mapping.client_ids,
                    'use_global_settings': True,
                    'filtering_enabled': True,
                    'safebrowsing_enabled': False,
                    'parental_enabled': False,
                    'safe_search': {'enabled': False},
                    'use_global_blocked_services': True,
                    'blocked_services': [],
                    'upstreams': [],
                    'ignore_querylog': False,
                    'ignore_statistics': False
                })
            
            return jsonify({
                'client_ids': mapping.client_ids,
                'use_global_settings': client_info.get('use_global_settings', True),
                'filtering_enabled': client_info.get('filtering_enabled', True),
                'safebrowsing_enabled': client_info.get('safebrowsing_enabled', False),
                'parental_enabled': client_info.get('parental_enabled', False),
                'safe_search': client_info.get('safe_search', {'enabled': False}),
                'use_global_blocked_services': client_info.get('use_global_blocked_services', True),
                'blocked_services': client_info.get('blocked_services', []),
                'upstreams': client_info.get('upstreams', []),
                'ignore_querylog': client_info.get('ignore_querylog', False),
                'ignore_statistics': client_info.get('ignore_statistics', False)
            })
            
        except Exception as e:
            return jsonify({'error': f'获取客户端信息失败：{str(e)}'}), 500
            
    elif request.method == 'PUT':
        data = request.get_json()
        use_global_settings = data.get('use_global_settings', True)
        filtering_enabled = data.get('filtering_enabled', True)
        safebrowsing_enabled = data.get('safebrowsing_enabled', False)
        parental_enabled = data.get('parental_enabled', False)
        safe_search = data.get('safe_search', {'enabled': False})
        use_global_blocked_services = data.get('use_global_blocked_services', True)
        blocked_services = data.get('blocked_services', [])
        upstreams = data.get('upstreams', [])
        ignore_querylog = data.get('ignore_querylog', False)
        ignore_statistics = data.get('ignore_statistics', False)
        
        # 只有管理员可以修改设备标识
        if current_user.is_admin:
            client_ids = data.get('client_ids', [])
        else:
            # 普通用户保持原有设备标识不变
            client_ids = mapping.client_ids
        
        try:
            # 更新AdGuardHome客户端
            adguard = AdGuardService()
            adguard.update_client(
                name=mapping.client_name,
                ids=client_ids,
                use_global_settings=use_global_settings,
                filtering_enabled=filtering_enabled,
                safebrowsing_enabled=safebrowsing_enabled,
                parental_enabled=parental_enabled,
                safe_search=safe_search,
                use_global_blocked_services=use_global_blocked_services,
                blocked_services=blocked_services,
                upstreams=upstreams,
                ignore_querylog=ignore_querylog,
                ignore_statistics=ignore_statistics
            )

            # 更新映射记录
            mapping.client_ids = client_ids

            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_client',
                target_type='client',
                target_id=mapping.client_name,
                details=f'更新客户端{mapping.client_name}配置'
            )
            db.session.add(log)

            db.session.commit()
            return jsonify({'message': '客户端更新成功'})

        except Exception as e:
            db.session.rollback()
            logging.error(f'更新客户端 {mapping.client_name} 失败: {str(e)}')
            return jsonify({'error': f'更新客户端失败：{str(e)}'}), 500