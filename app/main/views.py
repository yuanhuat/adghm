import logging
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog

from app.models.feedback import Feedback
from app.models.dns_config import DnsConfig
from app.services.adguard_service import AdGuardService

from app.admin.views import admin_required
from . import main
from flask import send_file
import os



@main.route('/')
@login_required
def index():
    """用户主页
    
    显示用户的客户端列表和基本信息，以及域名映射信息
    """

    
    # 获取当前用户的AdGuardHome客户端请求数量和总DNS查询数量
    user_request_count = 0
    total_dns_queries = 0
    try:
        adguard_service = AdGuardService()
        
        # 获取统计数据
        stats = adguard_service.get_stats()
        
        if stats:
            # 获取总DNS查询数量
            total_dns_queries = stats.get('num_dns_queries', 0)
            
            # 获取用户客户端请求数量
            if 'top_clients' in stats:
                # 查找当前用户的客户端
                user_clients = ClientMapping.query.filter_by(user_id=current_user.id).all()
                user_client_names = [client.client_name for client in user_clients]
                # 获取所有客户端ID
                user_client_ids = []
                for client in user_clients:
                    user_client_ids.extend(client.client_ids)
                
                # 在top_clients中查找用户的客户端请求数
                for client_stat in stats['top_clients']:
                    # top_clients格式: {"client_name": request_count}
                    for client_name, request_count in client_stat.items():
                        # 匹配客户端名称或客户端ID
                        if client_name in user_client_names or client_name in user_client_ids:
                            user_request_count += request_count
                        
    except Exception as e:
        logging.error(f"获取AdGuardHome统计数据失败: {str(e)}")
        user_request_count = 0
        total_dns_queries = 0
    
    return render_template('main/index.html', 
                         user_request_count=user_request_count,
                         total_dns_queries=total_dns_queries)






@main.route('/clients')
@login_required
def clients():
    """客户端管理页面
    
    显示用户的所有客户端及其详细信息
    """
    return render_template('main/clients.html')

@main.route('/guide')
@login_required
def guide():
    """AdGuardHome使用指南页面
    
    显示AdGuardHome的使用指南和帮助文档
    """
    return render_template('main/guide.html')

@main.route('/settings/change-password')
@login_required
def change_password_page():
    """修改密码页面
    
    显示修改密码的表单页面
    """
    return render_template('auth/change_password.html')

@main.route('/settings/change-email')
@login_required
def change_email_page():
    """修改邮箱页面
    
    显示修改邮箱的表单页面
    """
    return render_template('auth/change_email.html')

@main.route('/api/stats')
@login_required
def api_stats():
    """获取AdGuardHome统计数据的API接口
    
    返回JSON格式的统计数据，用于前端动态更新
    
    Returns:
        JSON: 包含用户请求数、总DNS查询数和用户排名的统计数据
    """
    user_request_count = 0
    total_dns_queries = 0
    user_ranking = 0
    total_clients = 0
    
    try:
        adguard_service = AdGuardService()
        
        # 获取统计数据
        stats = adguard_service.get_stats()
        
        if stats:
            # 获取总DNS查询数量
            total_dns_queries = stats.get('num_dns_queries', 0)
            
            # 获取用户客户端请求数量和排名
            if 'top_clients' in stats:
                # 查找当前用户的客户端
                user_clients = ClientMapping.query.filter_by(user_id=current_user.id).all()
                user_client_names = [client.client_name for client in user_clients]
                user_client_ids = []
                for client in user_clients:
                    user_client_ids.extend(client.client_ids)
                
                # 构建所有客户端的请求数列表，用于排名计算
                all_clients_requests = []
                
                # 在top_clients中查找用户的客户端请求数
                for client_stat in stats['top_clients']:
                    # top_clients格式: {"client_name": request_count}
                    for client_name, request_count in client_stat.items():
                        all_clients_requests.append(request_count)
                        # 检查客户端名称或客户端ID是否匹配
                        if client_name in user_client_names or client_name in user_client_ids:
                            user_request_count += request_count
                
                # 计算用户排名
                if all_clients_requests:
                    # 按请求数降序排序
                    all_clients_requests.sort(reverse=True)
                    total_clients = len(all_clients_requests)
                    
                    # 查找用户请求数在排序列表中的位置
                    if user_request_count > 0:
                        for i, count in enumerate(all_clients_requests):
                            if count <= user_request_count:
                                user_ranking = i + 1
                                break
                        if user_ranking == 0:  # 如果没找到，说明用户排在最后
                            user_ranking = total_clients
                        
    except Exception as e:
        logging.error(f"API获取AdGuardHome统计数据失败: {str(e)}")
        user_request_count = 0
        total_dns_queries = 0
        user_ranking = 0
        total_clients = 0
    
    return jsonify({
        'user_request_count': user_request_count,
        'total_dns_queries': total_dns_queries,
        'user_ranking': user_ranking,
        'total_clients': total_clients
    })

@main.route('/api/client_list')
@login_required
def client_list():
    """获取当前用户的客户端列表"""
    client_mappings = ClientMapping.query.filter_by(user_id=current_user.id).all()
    return jsonify([m.to_dict() for m in client_mappings])


@main.route('/api/client_ranking')
@login_required
def api_client_ranking():
    """获取AdGuardHome客户端排行数据的API接口
    
    返回JSON格式的客户端排行数据，显示请求数量最多的客户端
    
    Returns:
        JSON: 包含客户端排行数据的列表
    """
    client_ranking = []
    
    try:
        import ipaddress
        adguard_service = AdGuardService()
        
        # 获取统计数据和所有客户端信息
        stats = adguard_service.get_stats()
        all_clients = adguard_service.get_all_clients()

        # 构建客户端IP到名称的映射
        client_map = {}
        client_cidrs = {}
        if all_clients:
            for client in all_clients:
                for cidr in client.get('ids', []):
                    try:
                        # 区分普通IP和CIDR
                        if '/' in cidr:
                            client_cidrs[ipaddress.ip_network(cidr, strict=False)] = client.get('name')
                        else:
                            client_map[cidr] = client.get('name')
                    except ValueError:
                        # 处理无效的CIDR或IP
                        client_map[cidr] = client.get('name')

        if stats and 'top_clients' in stats:
            # 处理top_clients数据
            for client_stat in stats['top_clients']:
                for client_ip, request_count in client_stat.items():
                    # 默认客户端名称为IP
                    client_name_from_map = client_ip
                    
                    # 首先在普通IP映射中查找
                    if client_ip in client_map:
                        client_name_from_map = client_map[client_ip]
                    else:
                        # 如果不在普通IP映射中，则检查CIDR范围
                        try:
                            ip = ipaddress.ip_address(client_ip)
                            for network, name in client_cidrs.items():
                                if ip in network:
                                    client_name_from_map = name
                                    break
                        except ValueError:
                            pass  # 不是有效的IP地址，保持原样

                    # 查找客户端对应的用户信息
                    client_mapping = ClientMapping.query.filter_by(client_name=client_name_from_map).first()
                    
                    client_info = {
                        'client_name': client_name_from_map,
                        'request_count': request_count,
                        'user_name': client_mapping.user.username if client_mapping else '未知用户',
                        'is_current_user': client_mapping.user_id == current_user.id if client_mapping else False
                    }
                    client_ranking.append(client_info)
            
            # 按请求数量降序排序
            client_ranking.sort(key=lambda x: x['request_count'], reverse=True)
            
            # 只返回前10名
            client_ranking = client_ranking[:10]
                        
    except Exception as e:
        logging.error(f"API获取客户端排行数据失败: {str(e)}")
        client_ranking = []
    
    return jsonify({
        'client_ranking': client_ranking
    })

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


@main.route('/global_blocked_services')
@login_required
@admin_required
def global_blocked_services_page():
    """全局阻止服务管理页面"""
    return render_template('main/global_blocked_services.html')

@main.route('/api/global_blocked_services', methods=['GET', 'PUT'])
@login_required
@admin_required
def api_global_blocked_services():
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


@main.route('/api/feedback', methods=['GET', 'POST'])
@login_required
def api_feedback():
    """留言反馈API接口
    
    GET: 获取当前用户的留言列表
    POST: 创建新的留言
    
    Returns:
        JSON: 操作结果或留言列表
    """
    if request.method == 'GET':
        try:
            # 获取当前用户的留言列表，按创建时间倒序
            feedbacks = Feedback.query.filter_by(user_id=current_user.id).order_by(Feedback.created_at.desc()).all()
            
            feedback_list = [feedback.to_dict() for feedback in feedbacks]
            
            return jsonify({
                'success': True,
                'feedbacks': feedback_list
            })
        except Exception as e:
            logging.error(f"获取留言列表失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'获取留言列表失败: {str(e)}'
            }), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            title = data.get('title', '').strip()
            content = data.get('content', '').strip()
            
            # 验证输入
            if not title:
                return jsonify({
                    'success': False,
                    'error': '留言标题不能为空'
                }), 400
            
            if not content:
                return jsonify({
                    'success': False,
                    'error': '留言内容不能为空'
                }), 400
            
            if len(title) > 200:
                return jsonify({
                    'success': False,
                    'error': '留言标题不能超过200个字符'
                }), 400
            
            if len(content) > 2000:
                return jsonify({
                    'success': False,
                    'error': '留言内容不能超过2000个字符'
                }), 400
            
            # 创建新留言
            feedback = Feedback(
                user_id=current_user.id,
                title=title,
                content=content
            )
            
            db.session.add(feedback)
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='create_feedback',
                target_type='feedback',
                target_id=str(feedback.id),
                details=f'创建留言: {title}'
            )
            db.session.add(log)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '留言提交成功',
                'feedback': feedback.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            logging.error(f"创建留言失败: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'创建留言失败: {str(e)}'
            }), 500


@main.route('/api/dns-config')
@login_required
def api_dns_config():
    """获取DNS配置信息的API接口
    
    返回JSON格式的DNS配置数据，用于在用户主页显示DNS-over-QUIC和DNS-over-TLS配置
    服务器地址格式为：客户端ID.管理员设置的域名
    
    Returns:
        JSON: 包含DNS配置信息的数据
    """
    try:
        # 获取DNS配置
        config = DnsConfig.get_config()
        
        if not config:
            # 如果没有配置，返回默认值
            return jsonify({
                'display_title': 'DNS配置信息',
                'display_description': '',
                'doq_enabled': False,
                'doq_server': '',
                'doq_port': 853,
                'doq_description': '',
                'dot_enabled': False,
                'dot_server': '',
                'dot_port': 853,
                'dot_description': '',
                'doh_enabled': False,
                'doh_server': '',
                'doh_port': 443,
                'doh_path': '/dns-query',
                'doh_description': ''
            })
        
        # 获取用户的客户端映射，使用第一个客户端ID
        client_mapping = ClientMapping.query.filter_by(user_id=current_user.id).first()
        client_id = None
        
        if client_mapping and client_mapping.client_ids:
            # 使用第一个客户端ID
            client_id = client_mapping.client_ids[0] if client_mapping.client_ids else None
        
        # 构建用户专属的服务器地址：客户端ID.域名
        user_doq_server = ''
        user_dot_server = ''
        user_doh_server = ''
        
        if client_id:
            if config.doq_enabled and config.doq_server:
                user_doq_server = f"{client_id}.{config.doq_server}"
            
            if config.dot_enabled and config.dot_server:
                user_dot_server = f"{client_id}.{config.dot_server}"
            
            if config.doh_enabled and config.doh_server:
                user_doh_server = f"{client_id}.{config.doh_server}"
        else:
            # 如果没有客户端ID，使用原始服务器地址
            if config.doq_enabled and config.doq_server:
                user_doq_server = config.doq_server
            
            if config.dot_enabled and config.dot_server:
                user_dot_server = config.dot_server
            
            if config.doh_enabled and config.doh_server:
                user_doh_server = config.doh_server
        
        return jsonify({
            'display_title': config.display_title or 'DNS配置信息',
            'display_description': config.display_description or '',
            'doq_enabled': config.doq_enabled,
            'doq_server': user_doq_server,
            'doq_port': config.doq_port,
            'doq_description': config.doq_description or '',
            'dot_enabled': config.dot_enabled,
            'dot_server': user_dot_server,
            'dot_port': config.dot_port,
            'dot_description': config.dot_description or '',
            'doh_enabled': config.doh_enabled,
            'doh_server': user_doh_server,
            'doh_port': config.doh_port,
            'doh_path': config.doh_path or '/dns-query',
            'doh_description': config.doh_description or ''
        })
        
    except Exception as e:
        logging.error(f"获取DNS配置失败: {str(e)}")
        return jsonify({
            'error': f'获取DNS配置失败: {str(e)}'
        }), 500


@main.route('/api/apple/doh.mobileconfig')
@login_required
def apple_doh_mobileconfig():
    """生成DNS-over-HTTPS的苹果配置文件
    
    为当前用户生成DoH的.mobileconfig文件，使用管理员设置的域名和用户的客户端ID
    
    Returns:
        .mobileconfig文件下载
    """
    try:
        # 获取DNS配置
        config = DnsConfig.get_config()
        
        if not config or not config.doh_enabled or not config.doh_server:
            return jsonify({
                'error': 'DNS-over-HTTPS配置未启用或未设置'
            }), 400
        
        # 获取用户的客户端ID
        client_mapping = ClientMapping.query.filter_by(user_id=current_user.id).first()
        client_id = None
        
        if client_mapping and client_mapping.client_ids:
            client_id = client_mapping.client_ids[0]
        
        if not client_id:
            return jsonify({
                'error': '用户没有关联的客户端ID'
            }), 400
        
        # 构建DoH服务器地址
        doh_server = f"{client_id}.{config.doh_server}"
        doh_port = config.doh_port or 443
        doh_path = config.doh_path or '/dns-query'
        
        # 构建DoH URL
        if doh_port == 443:
            doh_url = f"https://{doh_server}{doh_path}"
        else:
            doh_url = f"https://{doh_server}:{doh_port}{doh_path}"
        
        # 生成.mobileconfig文件内容
        import uuid
        from datetime import datetime
        
        payload_uuid = str(uuid.uuid4()).upper()
        profile_uuid = str(uuid.uuid4()).upper()
        
        mobileconfig_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>DNSSettings</key>
            <dict>
                <key>DNSProtocol</key>
                <string>HTTPS</string>
                <key>ServerURL</key>
                <string>{doh_url}</string>
            </dict>
            <key>PayloadDescription</key>
            <string>Configures device to use AdGuard Home DNS-over-HTTPS</string>
            <key>PayloadDisplayName</key>
            <string>AdGuard Home DoH</string>
            <key>PayloadIdentifier</key>
            <string>com.adguardhome.doh.{client_id}</string>
            <key>PayloadType</key>
            <string>com.apple.dnsSettings.managed</string>
            <key>PayloadUUID</key>
            <string>{payload_uuid}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
        </dict>
    </array>
    <key>PayloadDescription</key>
    <string>AdGuard Home DNS-over-HTTPS configuration for {current_user.username}</string>
    <key>PayloadDisplayName</key>
    <string>AdGuard Home DoH - {current_user.username}</string>
    <key>PayloadIdentifier</key>
    <string>com.adguardhome.profile.doh.{client_id}</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{profile_uuid}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>'''
        
        # 创建响应
        from flask import Response
        response = Response(
            mobileconfig_content,
            mimetype='application/x-apple-aspen-config',
            headers={
                'Content-Disposition': f'attachment; filename="AdGuardHome-DoH-{client_id}.mobileconfig"'
            }
        )
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='download_apple_config',
            target_type='mobileconfig',
            target_id=f'doh-{client_id}',
            details=f'下载DoH配置文件: {doh_url}'
        )
        db.session.add(log)
        db.session.commit()
        
        return response
        
    except Exception as e:
        logging.error(f"生成DoH配置文件失败: {str(e)}")
        return jsonify({
            'error': f'生成DoH配置文件失败: {str(e)}'
        }), 500


@main.route('/api/apple/dot.mobileconfig')
@login_required
def apple_dot_mobileconfig():
    """生成DNS-over-TLS的苹果配置文件
    
    为当前用户生成DoT的.mobileconfig文件，使用管理员设置的域名和用户的客户端ID
    
    Returns:
        .mobileconfig文件下载
    """
    try:
        # 获取DNS配置
        config = DnsConfig.get_config()
        
        if not config or not config.dot_enabled or not config.dot_server:
            return jsonify({
                'error': 'DNS-over-TLS配置未启用或未设置'
            }), 400
        
        # 获取用户的客户端ID
        client_mapping = ClientMapping.query.filter_by(user_id=current_user.id).first()
        client_id = None
        
        if client_mapping and client_mapping.client_ids:
            client_id = client_mapping.client_ids[0]
        
        if not client_id:
            return jsonify({
                'error': '用户没有关联的客户端ID'
            }), 400
        
        # 构建DoT服务器地址
        dot_server = f"{client_id}.{config.dot_server}"
        dot_port = config.dot_port or 853
        
        # 生成.mobileconfig文件内容
        import uuid
        from datetime import datetime
        
        payload_uuid = str(uuid.uuid4()).upper()
        profile_uuid = str(uuid.uuid4()).upper()
        
        mobileconfig_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>DNSSettings</key>
            <dict>
                <key>DNSProtocol</key>
                <string>TLS</string>
                <key>ServerName</key>
                <string>{dot_server}</string>
                <key>ServerAddresses</key>
                <array>
                    <string>{dot_server}</string>
                </array>
            </dict>
            <key>PayloadDescription</key>
            <string>Configures device to use AdGuard Home DNS-over-TLS</string>
            <key>PayloadDisplayName</key>
            <string>AdGuard Home DoT</string>
            <key>PayloadIdentifier</key>
            <string>com.adguardhome.dot.{client_id}</string>
            <key>PayloadType</key>
            <string>com.apple.dnsSettings.managed</string>
            <key>PayloadUUID</key>
            <string>{payload_uuid}</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
        </dict>
    </array>
    <key>PayloadDescription</key>
    <string>AdGuard Home DNS-over-TLS configuration for {current_user.username}</string>
    <key>PayloadDisplayName</key>
    <string>AdGuard Home DoT - {current_user.username}</string>
    <key>PayloadIdentifier</key>
    <string>com.adguardhome.profile.dot.{client_id}</string>
    <key>PayloadRemovalDisallowed</key>
    <false/>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>{profile_uuid}</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>'''
        
        # 创建响应
        from flask import Response
        response = Response(
            mobileconfig_content,
            mimetype='application/x-apple-aspen-config',
            headers={
                'Content-Disposition': f'attachment; filename="AdGuardHome-DoT-{client_id}.mobileconfig"'
            }
        )
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='download_apple_config',
            target_type='mobileconfig',
            target_id=f'dot-{client_id}',
            details=f'下载DoT配置文件: {dot_server}:{dot_port}'
        )
        db.session.add(log)
        db.session.commit()
        
        return response
        
    except Exception as e:
        logging.error(f"生成DoT配置文件失败: {str(e)}")
        return jsonify({
            'error': f'生成DoT配置文件失败: {str(e)}'
        }), 500