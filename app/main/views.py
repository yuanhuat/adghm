import logging
from flask import render_template, redirect, url_for, flash, request, jsonify, send_from_directory, Response
from flask_login import login_required, current_user
from app import db
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog
from app.models.announcement import Announcement

from app.models.feedback import Feedback
from app.models.dns_config import DnsConfig
from app.models.donation_config import DonationConfig
from app.models.donation_record import DonationRecord
from app.models.vip_config import VipConfig
from app.services.adguard_service import AdGuardService
from app.utils.seo_config import get_page_seo, get_structured_data

from app.admin.views import admin_required
from . import main
from flask import send_file
import os



@main.route('/dashboard')
@login_required
def dashboard():
    """用户主页
    
    显示用户的客户端列表和基本信息，以及域名映射信息
    """
    # 获取当前用户的AdGuardHome客户端请求数量和总DNS查询数量
    user_request_count = 0
    total_dns_queries = 0
    total_blocked_queries = 0
    try:
        adguard_service = AdGuardService()
        
        # 获取统计数据
        stats = adguard_service.get_stats()
        
        if stats:
            # 获取总DNS查询数量
            total_dns_queries = stats.get('num_dns_queries', 0)
            
            # 获取总拦截数量（包括所有类型的拦截）
            total_blocked_queries = (
                stats.get('num_blocked_filtering', 0) +
                stats.get('num_replaced_safebrowsing', 0) +
                stats.get('num_replaced_safesearch', 0) +
                stats.get('num_replaced_parental', 0)
            )
            
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
        total_blocked_queries = 0
    
    seo_config = get_page_seo('dashboard')
    structured_data = get_structured_data('dashboard')
    return render_template('main/dashboard.html', 
                         user_request_count=user_request_count,
                         total_dns_queries=total_dns_queries,
                         total_blocked_queries=total_blocked_queries,
                         seo_config=seo_config,
                         structured_data=structured_data)

@main.route('/')
def index():
    """主页
    
    根据用户登录状态显示不同内容：
    - 已登录用户：重定向到仪表板
    - 未登录用户：显示宣传页面
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    seo_config = get_page_seo('landing')
    structured_data = get_structured_data('landing')
    return render_template('main/landing.html', 
                         seo_config=seo_config, 
                         structured_data=structured_data)

@main.route('/landing')
def landing():
    """宣传页面首页
    
    显示产品介绍和功能特性
    """
    seo_config = get_page_seo('landing')
    structured_data = get_structured_data('landing')
    return render_template('main/landing.html', 
                         seo_config=seo_config, 
                         structured_data=structured_data)

@main.route('/about')
def about():
    """关于我们页面
    
    显示公司介绍、团队信息和联系方式
    """
    seo_config = get_page_seo('about')
    structured_data = get_structured_data('about')
    return render_template('main/about.html', 
                         seo_config=seo_config, 
                         structured_data=structured_data)

@main.route('/features')
def features():
    """功能特性页面
    
    详细展示产品功能和技术优势
    """
    seo_config = get_page_seo('features')
    structured_data = get_structured_data('features')
    return render_template('main/features.html', 
                         seo_config=seo_config, 
                         structured_data=structured_data)

@main.route('/guide')
def guide():
    """使用指南页面
    
    提供产品使用教程和帮助文档
    """
    # 获取捐赠配置（用于显示排行榜链接）
    donation_config = DonationConfig.get_config()
    seo_config = get_page_seo('guide')
    structured_data = get_structured_data('guide')
    return render_template('main/guide.html', 
                         donation_config=donation_config,
                         seo_config=seo_config, 
                         structured_data=structured_data)

@main.route('/pricing')
def pricing():
    """价格方案页面
    
    展示不同服务套餐和定价信息
    """
    seo_config = get_page_seo('pricing')
    structured_data = get_structured_data('pricing')
    return render_template('main/pricing.html', 
                         seo_config=seo_config, 
                         structured_data=structured_data)

@main.route('/clients')
@login_required
def clients():
    """客户端管理页面
    
    显示用户的所有客户端及其详细信息
    """
    seo_config = get_page_seo('clients')
    structured_data = get_structured_data('clients')
    return render_template('main/clients.html', 
                         seo_config=seo_config, 
                         structured_data=structured_data)



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
    total_blocked_queries = 0
    user_ranking = 0
    total_clients = 0
    
    try:
        adguard_service = AdGuardService()
        
        # 获取统计数据
        stats = adguard_service.get_stats()
        
        if stats:
            # 获取总DNS查询数量
            total_dns_queries = stats.get('num_dns_queries', 0)
            
            # 获取总拦截数量（包括所有类型的拦截）
            total_blocked_queries = (
                stats.get('num_blocked_filtering', 0) +
                stats.get('num_replaced_safebrowsing', 0) +
                stats.get('num_replaced_safesearch', 0) +
                stats.get('num_replaced_parental', 0)
            )
            
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
        total_blocked_queries = 0
        user_ranking = 0
        total_clients = 0
    
    return jsonify({
        'user_request_count': user_request_count,
        'total_dns_queries': total_dns_queries,
        'total_blocked_queries': total_blocked_queries,
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
        
        # 构建用户专属的服务器地址
        user_doq_server = ''
        user_dot_server = ''
        user_doh_server = ''
        user_doh_path = ''
        
        if client_id:
            if config.doq_enabled and config.doq_server:
                user_doq_server = f"{client_id}.{config.doq_server}"
            
            if config.dot_enabled and config.dot_server:
                user_dot_server = f"{client_id}.{config.dot_server}"
            
            if config.doh_enabled and config.doh_server:
                # DoH服务器地址包含客户端ID作为子域名
                user_doh_server = f"{client_id}.{config.doh_server}"
                # 路径不包含客户端ID
                user_doh_path = config.doh_path or '/dns-query'
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
            'doh_path': user_doh_path or (config.doh_path or '/dns-query'),
            'doh_description': config.doh_description or '',
            # 添加苹果配置控制字段
            'apple_config_enabled': config.apple_config_enabled,
            'apple_doh_config_enabled': config.apple_doh_config_enabled,
            'apple_dot_config_enabled': config.apple_dot_config_enabled
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
    根据AdGuard Home API要求，host参数现在是必需的
    
    Returns:
        .mobileconfig文件下载
    """
    try:
        # 获取host参数（必需）
        host = request.args.get('host')
        if not host:
            return jsonify({
                'error': 'host参数是必需的，请提供DNS服务器的主机名'
            }), 400
        
        # 获取DNS配置
        config = DnsConfig.get_config()
        
        if not config or not config.doh_enabled or not config.doh_server:
            return jsonify({
                'error': 'DNS-over-HTTPS配置未启用或未设置'
            }), 400
        
        # 检查管理员是否启用了苹果配置文件功能
        if not config.apple_config_enabled or not config.apple_doh_config_enabled:
            return jsonify({
                'error': '管理员已禁用苹果设备DoH配置文件下载功能'
            }), 403
        
        # 获取用户的客户端ID
        client_mapping = ClientMapping.query.filter_by(user_id=current_user.id).first()
        client_id = None
        
        if client_mapping and client_mapping.client_ids:
            client_id = client_mapping.client_ids[0]
        
        if not client_id:
            return jsonify({
                'error': '用户没有关联的客户端ID'
            }), 400
        
        # 验证客户端ID格式（AdGuard Home要求：[0-9a-z-]{1,64}）
        import re
        if not re.match(r'^[0-9a-z-]{1,64}$', client_id):
            return jsonify({
                'error': f'客户端ID格式无效：{client_id}，必须是1-64位的小写字母、数字或连字符'
            }), 400
        
        # 构建DoH服务器地址（使用host参数）
        doh_server = host.strip()
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
        
        payload_uuid = str(uuid.uuid4())
        payload_identifier_uuid = str(uuid.uuid4())
        profile_uuid = str(uuid.uuid4())
        profile_identifier_uuid = str(uuid.uuid4())
        
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
    根据AdGuard Home API要求，host参数现在是必需的
    
    Returns:
        .mobileconfig文件下载
    """
    try:
        # 获取host参数（必需）
        host = request.args.get('host')
        if not host:
            return jsonify({
                'error': 'host参数是必需的，请提供DNS服务器的主机名'
            }), 400
        
        # 获取DNS配置
        config = DnsConfig.get_config()
        
        if not config or not config.dot_enabled or not config.dot_server:
            return jsonify({
                'error': 'DNS-over-TLS配置未启用或未设置'
            }), 400
        
        # 检查管理员是否启用了苹果配置文件功能
        if not config.apple_config_enabled or not config.apple_dot_config_enabled:
            return jsonify({
                'error': '管理员已禁用苹果设备DoT配置文件下载功能'
            }), 403
        
        # 获取用户的客户端ID
        client_mapping = ClientMapping.query.filter_by(user_id=current_user.id).first()
        client_id = None
        
        if client_mapping and client_mapping.client_ids:
            client_id = client_mapping.client_ids[0]
        
        if not client_id:
            return jsonify({
                'error': '用户没有关联的客户端ID'
            }), 400
        
        # 验证客户端ID格式（AdGuard Home要求：[0-9a-z-]{1,64}）
        import re
        if not re.match(r'^[0-9a-z-]{1,64}$', client_id):
            return jsonify({
                'error': f'客户端ID格式无效：{client_id}，必须是1-64位的小写字母、数字或连字符'
            }), 400
        
        # 构建DoT服务器地址（使用host参数）
        # 注意：与DoH不同，DoT协议不支持路径参数，因此无法使用路径格式 (server:port/path/client_id)
        # 根据AdGuard Home的实际格式，DoT使用客户端ID+域名格式 (client_id.server:port)
        dot_server = f"{client_id}.{host.strip()}"
        dot_port = config.dot_port or 853
        
        # 生成.mobileconfig文件内容
        import uuid
        from datetime import datetime
        
        payload_uuid = str(uuid.uuid4())
        payload_identifier_uuid = str(uuid.uuid4())
        profile_uuid = str(uuid.uuid4())
        profile_identifier_uuid = str(uuid.uuid4())
        
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
				</dict>
				<key>PayloadDescription</key>
				<string>Configures device to use AdGuard Home</string>
				<key>PayloadDisplayName</key>
				<string>{host.strip()} DoT</string>
				<key>PayloadIdentifier</key>
				<string>com.apple.dnsSettings.managed.{payload_identifier_uuid.lower()}</string>
				<key>PayloadType</key>
				<string>com.apple.dnsSettings.managed</string>
				<key>PayloadUUID</key>
				<string>{payload_uuid.lower()}</string>
				<key>PayloadVersion</key>
				<integer>1</integer>
			</dict>
		</array>
		<key>PayloadDescription</key>
		<string>Adds AdGuard Home to macOS Big Sur and iOS 14 or newer systems</string>
		<key>PayloadDisplayName</key>
		<string>{host.strip()} DoT</string>
		<key>PayloadIdentifier</key>
		<string>{profile_identifier_uuid.lower()}</string>
		<key>PayloadRemovalDisallowed</key>
		<false/>
		<key>PayloadType</key>
		<string>Configuration</string>
		<key>PayloadUUID</key>
		<string>{profile_uuid.lower()}</string>
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

@main.route('/api/announcements/active')
@login_required
def get_announcements():
    """获取首页公告"""
    try:
        # 获取启用且在首页显示的公告
        announcements = Announcement.query.filter_by(
            is_active=True,
            show_on_homepage=True
        ).order_by(Announcement.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'announcements': [announcement.to_dict() for announcement in announcements]
        })
    except Exception as e:
        logging.error(f"获取公告失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@main.route('/dns-test')
def dns_test():
    """DNS检测页面 - 显示DNS重写成功页面
    
    如果用户能访问到这个页面，说明DNS重写已经生效
    （test.dns.con这个不存在的域名被成功重写到服务器IP）
    """
    # 能访问到这里就说明DNS重写生效了
    return render_template('main/dns_test.html')


@main.route('/donation')
def donation():
    """捐赠页面
    
    显示捐赠表单，允许用户进行捐赠
    """
    # 获取捐赠配置
    config = DonationConfig.get_config()
    
    # 检查捐赠功能是否启用且配置完整
    if not config.enabled or not config.is_configured():
        flash('捐赠功能暂时不可用', 'info')
        return redirect(url_for('main.dashboard'))
    
    # 获取VIP配置
    vip_config = VipConfig.get_config()
    
    # 获取当前用户的客户端名称作为默认捐赠者姓名
    default_donor_name = ''
    user_vip_status = None
    if current_user.is_authenticated:
        try:
            client_mapping = ClientMapping.query.filter_by(user_id=current_user.id).first()
            if client_mapping:
                default_donor_name = client_mapping.client_name
            
            # 获取用户VIP状态信息
            user_vip_status = {
                'is_vip': current_user.is_vip(),
                'vip_expire_time': current_user.vip_expire_time,
                'total_donation': float(current_user.total_donation or 0)
            }
        except Exception as e:
            logging.error(f"获取用户信息失败: {str(e)}")
    
    return render_template('main/donation.html', 
                         config=config,
                         vip_config=vip_config,
                         min_amount=float(config.min_amount),
                         max_amount=float(config.max_amount),
                         donation_enabled=True,
                         donation_description=config.donation_description,
                         default_donor_name=default_donor_name,
                         user_vip_status=user_vip_status)


@main.route('/api/donation/create', methods=['POST'])
def create_donation():
    """创建捐赠订单API
    
    处理用户的捐赠请求，创建支付订单
    """
    try:
        # 获取捐赠配置
        config = DonationConfig.get_config()
        
        # 检查捐赠功能是否启用且配置完整
        if not config.enabled or not config.is_configured():
            return jsonify({
                'success': False,
                'error': '捐赠功能暂时不可用'
            }), 400
        
        # 获取请求数据
        data = request.get_json()
        amount = float(data.get('amount', 0))
        donor_name = data.get('donor_name', '').strip()
        payment_type = data.get('payment_type', '').strip()
        message = data.get('message', '').strip()
        
        # 验证捐赠金额
        if amount < config.min_amount or amount > config.max_amount:
            return jsonify({
                'success': False,
                'error': f'捐赠金额必须在 {config.min_amount} 到 {config.max_amount} 之间'
            }), 400
        
        # 验证支付方式
        if payment_type not in ['alipay', 'wxpay']:
            return jsonify({
                'success': False,
                'error': '请选择有效的支付方式'
            }), 400
        
        # 生成订单号
        import uuid
        import time
        order_id = f"DONATE_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        # 构建支付参数
        import hashlib
        from urllib.parse import urlencode
        
        # 当前域名作为回调地址
        base_url = request.url_root.rstrip('/')
        
        # 使用配置的回调地址，如果没有配置则使用默认地址
        if config.notify_url:
            notify_url = config.notify_url
        else:
            notify_url = f"{base_url}/donation/callback"
            
        if config.return_url:
            return_url = config.return_url
        else:
            return_url = f"{base_url}/donation/return"
        
        # 支付参数（按照彩虹易支付SDK的参数格式）
        pay_params = {
            'pid': config.merchant_id,
            'type': payment_type,
            'out_trade_no': order_id,
            'notify_url': notify_url,
            'return_url': return_url,
            'name': f'捐赠支持 - {donor_name}' if donor_name else '捐赠支持',
            'money': f'{amount:.2f}'
        }
        
        # 生成签名（按照彩虹易支付SDK的签名算法）
        # 按字典序排序参数（除了sign和sign_type）
        sorted_params = sorted(pay_params.items())
        sign_string = '&'.join([f'{k}={v}' for k, v in sorted_params if v != ''])
        sign_string += config.api_key
        sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
        pay_params['sign'] = sign
        pay_params['sign_type'] = 'MD5'
        
        # 创建捐赠记录
        donation_record = DonationRecord(
            order_id=order_id,
            donor_name=donor_name if donor_name else '匿名捐赠者',
            amount=amount,
            payment_type=payment_type,
            status='pending',
            user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(donation_record)
        
        # 记录操作日志
        if current_user.is_authenticated:
            log = OperationLog(
                user_id=current_user.id,
                operation_type='create_donation',
                target_type='donation',
                target_id=order_id,
                details=f'创建捐赠订单：金额={amount}，支付方式={payment_type}，捐赠者={donor_name}'
            )
            db.session.add(log)
        
        db.session.commit()
        
        # 构建支付表单HTML（直接调用submit.php接口）
        form_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>正在跳转到支付页面...</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .loading {{ font-size: 18px; color: #666; }}
                .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 2s linear infinite; margin: 20px auto; }}
                @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            </style>
        </head>
        <body>
            <div class="spinner"></div>
            <div class="loading">正在跳转到支付页面，请稍候...</div>
            <form id="payForm" method="post" action="{config.api_url}">
        '''
        
        # 直接使用EpayCore期望的参数格式（不需要WID前缀）
        for key, value in pay_params.items():
            form_html += f'<input type="hidden" name="{key}" value="{value}" />\n'
        
        form_html += '''
            </form>
            <script>
                document.getElementById('payForm').submit();
            </script>
        </body>
        </html>
        '''
        
        return form_html
        
    except Exception as e:
        logging.error(f"创建捐赠订单失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'创建捐赠订单失败：{str(e)}'
        }), 500


@main.route('/api/adguard/blocked_services')
@login_required
@admin_required
def api_adguard_blocked_services():
    """获取AdGuard Home可用的阻止服务列表
    
    Returns:
        JSON响应，包含可用的阻止服务列表
    """
    try:
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
            services = [
                {"id": "facebook", "name": "Facebook"},
                {"id": "twitter", "name": "Twitter"},
                {"id": "youtube", "name": "YouTube"},
                {"id": "instagram", "name": "Instagram"},
                {"id": "netflix", "name": "Netflix"},
                {"id": "whatsapp", "name": "WhatsApp"},
                {"id": "tiktok", "name": "TikTok"},
                {"id": "snapchat", "name": "Snapchat"},
                {"id": "discord", "name": "Discord"},
                {"id": "reddit", "name": "Reddit"}
            ]
        
        return jsonify({
            'success': True,
            'services': services
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取阻止服务列表失败：{str(e)}'
        }), 500


@main.route('/api/adguard/clients/<client_name>')
@login_required
@admin_required
def api_adguard_client_get(client_name):
    """获取指定客户端的详细信息
    
    Args:
        client_name: 客户端名称
        
    Returns:
        JSON响应，包含客户端的详细配置信息
    """
    try:
        adguard = AdGuardService()
        client = adguard.find_client(client_name)
        
        if not client:
            return jsonify({
                'success': False,
                'message': f'未找到客户端：{client_name}'
            }), 404
        
        return jsonify({
            'success': True,
            'client': client
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取客户端信息失败：{str(e)}'
        }), 500


@main.route('/api/adguard/clients/<client_name>', methods=['PUT'])
@login_required
@admin_required
def api_adguard_client_update(client_name):
    """更新指定客户端的配置
    
    Args:
        client_name: 客户端名称
        
    Returns:
        JSON响应，表示更新是否成功
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        adguard = AdGuardService()
        
        # 构建更新数据
        update_data = {
            'name': client_name,
            'data': data
        }
        
        # 调用AdGuard Home API更新客户端
        result = adguard.update_client(update_data)
        
        if result:
            return jsonify({
                'success': True,
                'message': '客户端配置更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '客户端配置更新失败'
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'更新客户端配置失败：{str(e)}'
        }), 500


@main.route('/donation/success')
def donation_success():
    """捐赠支付成功页面
    
    用户支付完成后的跳转页面
    """
    return render_template('main/donation_success.html')


@main.route('/donation/ranking')
def donation_ranking():
    """捐赠排行榜页面
    
    显示捐赠者排行榜和最近捐赠记录
    """
    # 获取捐赠配置
    from app.models.donation_config import DonationConfig
    config = DonationConfig.get_config()
    
    # 获取排行榜数据（前20名）
    leaderboard = DonationRecord.get_leaderboard(limit=20)
    
    # 获取最近捐赠记录（前10条）
    recent_donations = DonationRecord.get_recent_donations(limit=10)
    
    # 获取统计数据
    total_amount = DonationRecord.get_total_amount()
    total_count = DonationRecord.get_total_count()
    
    return render_template('main/donation_ranking.html', 
                         leaderboard=leaderboard,
                         recent_donations=recent_donations,
                         total_amount=total_amount,
                         total_count=total_count,
                         hide_amount=config.hide_amount if config else False)


@main.route('/donation/return', methods=['GET'])
def donation_return():
    """捐赠支付同步回调接口
    
    处理支付平台的同步跳转回调，验证支付状态后跳转到相应页面
    """
    try:
        # 获取回调参数
        data = request.args.to_dict()
        
        # 获取捐赠配置用于验证签名
        config = DonationConfig.get_config()
        
        # 验证签名
        received_sign = data.get('sign', '')
        # 排除sign和sign_type参数，跳过空值
        calc_params = {k: v for k, v in data.items() if k not in ['sign', 'sign_type'] and v != ''}
        sorted_params = sorted(calc_params.items())
        sign_string = '&'.join([f'{k}={v}' for k, v in sorted_params]) + config.api_key
        
        import hashlib
        calculated_sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
        
        # 验证签名（使用多种可能的密钥）
        def verify_signature_with_multiple_keys(params, received_sign):
            possible_keys = [
                config.api_key,  # 当前配置的密钥
                'WWc3Z2jkK7jhNGPALcGKjHLPK47wRK85',  # SDK中的密钥
                '',  # 空密钥
                '1013',  # 商户ID
            ]
            
            for key in possible_keys:
                calc_params = {k: v for k, v in params.items() if k not in ['sign', 'sign_type'] and v != ''}
                sorted_params = sorted(calc_params.items())
                sign_string = '&'.join([f'{k}={v}' for k, v in sorted_params]) + key
                calculated_sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
                
                if received_sign.lower() == calculated_sign.lower():
                    logging.info(f'签名验证成功，使用密钥: {key[:10]}...')
                    return True
            
            logging.warning(f'所有密钥都无法验证签名，接收签名: {received_sign}')
            return False
        
        if not verify_signature_with_multiple_keys(data, received_sign):
            logging.warning(f"捐赠同步回调签名验证失败：订单ID={data.get('out_trade_no')}")
            flash('支付验证失败，请联系管理员', 'error')
            return redirect(url_for('main.donation'))
        
        order_id = data.get('out_trade_no')
        trade_status = data.get('trade_status')
        amount = data.get('money')
        
        if trade_status == 'TRADE_SUCCESS':
            # 支付成功
            logging.info(f"捐赠支付成功（同步回调）：订单ID={order_id}，金额={amount}")
            flash('捐赠支付成功，感谢您的支持！', 'success')
            return redirect(url_for('main.donation_success'))
        else:
            # 支付失败或其他状态
            logging.warning(f"捐赠支付失败（同步回调）：订单ID={order_id}，状态={trade_status}")
            flash('支付失败或已取消，请重试', 'error')
            return redirect(url_for('main.donation'))
            
    except Exception as e:
        logging.error(f"处理捐赠同步回调失败: {str(e)}")
        flash('支付状态验证失败，请联系管理员', 'error')
        return redirect(url_for('main.donation'))


@main.route('/donation/callback', methods=['GET', 'POST'])
def donation_callback():
    """捐赠支付回调接口
    
    处理支付平台的回调通知
    """
    try:
        # 获取回调数据（支持GET和POST两种方式）
        if request.method == 'GET':
            data = request.args.to_dict()
        else:
            data = request.form.to_dict()
        
        # 获取捐赠配置用于验证签名
        config = DonationConfig.get_config()
        
        # 验证签名
        received_sign = data.get('sign', '')
        # 排除sign和sign_type参数，跳过空值
        calc_params = {k: v for k, v in data.items() if k not in ['sign', 'sign_type'] and v != ''}
        sorted_params = sorted(calc_params.items())
        sign_string = '&'.join([f'{k}={v}' for k, v in sorted_params]) + config.api_key
        
        import hashlib
        calculated_sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
        
        # 验证签名（使用多种可能的密钥）
        def verify_signature_with_multiple_keys(params, received_sign):
            possible_keys = [
                config.api_key,  # 当前配置的密钥
                'WWc3Z2jkK7jhNGPALcGKjHLPK47wRK85',  # SDK中的密钥
                '',  # 空密钥
                '1013',  # 商户ID
            ]
            
            for key in possible_keys:
                calc_params = {k: v for k, v in params.items() if k not in ['sign', 'sign_type'] and v != ''}
                sorted_params = sorted(calc_params.items())
                sign_string = '&'.join([f'{k}={v}' for k, v in sorted_params]) + key
                calculated_sign = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
                
                if received_sign.lower() == calculated_sign.lower():
                    logging.info(f'签名验证成功，使用密钥: {key[:10]}...')
                    return True
            
            logging.warning(f'所有密钥都无法验证签名，接收签名: {received_sign}')
            return False
        
        if not verify_signature_with_multiple_keys(data, received_sign):
            logging.warning(f"捐赠回调签名验证失败：订单ID={data.get('out_trade_no')}")
            return 'FAIL'
        
        order_id = data.get('out_trade_no')
        trade_status = data.get('trade_status')
        amount = data.get('money')
        
        if trade_status == 'TRADE_SUCCESS':
            # 支付成功，更新捐赠记录
            from app.utils.timezone import beijing_time
            donation_record = DonationRecord.query.filter_by(order_id=order_id).first()
            if donation_record:
                donation_record.status = 'success'
                donation_record.trade_no = data.get('trade_no', '')
                donation_record.paid_at = beijing_time()
                db.session.commit()
                logging.info(f"捐赠支付成功：订单ID={order_id}，金额={amount}，捐赠者={donation_record.donor_name}")
            else:
                logging.warning(f"未找到捐赠记录：订单ID={order_id}")
            return 'SUCCESS'
        else:
            # 支付失败或其他状态，更新记录状态
            donation_record = DonationRecord.query.filter_by(order_id=order_id).first()
            if donation_record:
                donation_record.status = 'failed'
                db.session.commit()
            logging.warning(f"捐赠支付状态异常：订单ID={order_id}，状态={trade_status}")
            return 'FAIL'
            
    except Exception as e:
        logging.error(f"处理捐赠回调失败: {str(e)}")
        return 'FAIL'


@main.route('/sitemap.xml')
def sitemap():
    """提供XML网站地图"""
    try:
        return send_from_directory('static', 'sitemap.xml', mimetype='application/xml')
    except FileNotFoundError:
        return Response('Sitemap not found', status=404)


@main.route('/robots.txt')
def robots():
    """提供robots.txt文件"""
    try:
        return send_from_directory('static', 'robots.txt', mimetype='text/plain')
    except FileNotFoundError:
        return Response('Robots.txt not found', status=404)


@main.route('/api/clients/create', methods=['POST'])
@login_required
def api_create_client():
    """VIP用户创建新客户端API"""
    try:
        # 检查用户是否为VIP
        if not current_user.is_vip:
            return jsonify({
                'success': False,
                'message': '只有VIP用户才能创建新客户端'
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '请求数据格式错误'
            }), 400
        
        client_name = data.get('client_name', '').strip()
        client_id = data.get('client_id', '').strip()
        tags = data.get('tags', ['user_child'])  # 默认使用user_child标签
        
        if not client_name or not client_id:
            return jsonify({
                'success': False,
                'message': '客户端名称和客户端ID不能为空'
            }), 400
        
        # 验证标签格式
        if not isinstance(tags, list):
            return jsonify({
                'success': False,
                'message': '标签格式错误'
            }), 400
        
        # 检查客户端名称是否已存在（同一用户下）
        existing_mapping = ClientMapping.query.filter_by(
            user_id=current_user.id,
            client_name=client_name
        ).first()
        
        if existing_mapping:
            return jsonify({
                'success': False,
                'message': '客户端名称已存在，请使用其他名称'
            }), 400
        
        # 初始化AdGuard服务
        adguard = AdGuardService()
        
        # 检查AdGuard连接
        if not adguard.check_connection():
            return jsonify({
                'success': False,
                'message': '无法连接到AdGuardHome服务器，请联系管理员'
            }), 500
        
        try:
            # 使用与注册时相同的逻辑创建客户端
            client_ids = [client_id]  # 使用用户提供的客户端ID
            
            # 根据标签设置客户端配置
            parental_enabled = 'user_child' in tags  # 如果包含user_child标签，启用家长控制
            
            # 创建AdGuardHome客户端，使用安全的默认配置
            client_response = adguard.create_client(
                name=client_name,
                ids=client_ids,
                use_global_settings=True,  # 使用全局设置
                filtering_enabled=True,
                safebrowsing_enabled=True,  # 启用安全浏览
                parental_enabled=parental_enabled,  # 根据标签决定是否启用家长控制
                safe_search={  # 启用安全搜索
                    "enabled": True,
                    "bing": True,
                    "duckduckgo": True,
                    "google": True,
                    "pixabay": True,
                    "yandex": True,
                    "youtube": True
                },
                use_global_blocked_services=True,  # 使用全局屏蔽服务设置
                tags=tags,  # 传递标签
                ignore_querylog=False,
                ignore_statistics=False
            )
            
            # 将客户端加入允许列表
            try:
                # 获取当前的访问控制列表
                access_list = adguard._make_request('GET', '/access/list')
                allowed_clients = access_list.get('allowed_clients', [])
                
                # 将新客户端ID添加到允许列表
                if client_id not in allowed_clients:
                    allowed_clients.append(client_id)
                    
                    # 更新访问控制列表
                    access_data = {
                        'allowed_clients': allowed_clients,
                        'disallowed_clients': access_list.get('disallowed_clients', []),
                        'blocked_hosts': access_list.get('blocked_hosts', [])
                    }
                    adguard._make_request('POST', '/access/set', json=access_data)
                    logging.info(f"已将客户端 {client_id} 添加到允许列表")
            except Exception as e:
                logging.warning(f"将客户端添加到允许列表失败: {str(e)}")
                # 继续执行，不影响客户端创建流程
            
            # 创建客户端映射
            client_mapping = ClientMapping(
                user_id=current_user.id,
                client_name=client_name,
                client_ids=client_ids
            )
            db.session.add(client_mapping)
            db.session.commit()
            
            # 记录操作日志
            operation_log = OperationLog(
                user_id=current_user.id,
                operation_type='CREATE',
                target_type='CLIENT',
                target_id=client_id,
                details=f'VIP用户创建新客户端: {client_name} ({client_id})'
            )
            db.session.add(operation_log)
            db.session.commit()
            
            logging.info(f"VIP用户 {current_user.username} 成功创建客户端: {client_name} ({client_id})")
            
            return jsonify({
                'success': True,
                'message': '客户端创建成功',
                'client': {
                    'name': client_name,
                    'id': client_id
                }
            })
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"创建AdGuard客户端失败: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'创建客户端失败: {str(e)}'
            }), 500
            
    except Exception as e:
        logging.error(f"VIP用户创建客户端API错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500


@main.route('/api/clients/<int:mapping_id>', methods=['DELETE'])
@login_required
def api_delete_client(mapping_id):
    """VIP用户删除客户端API"""
    try:
        # 检查用户是否为VIP
        if not current_user.is_vip:
            return jsonify({
                'success': False,
                'message': '只有VIP用户才能删除客户端'
            }), 403
        
        # 获取客户端映射
        mapping = ClientMapping.query.get_or_404(mapping_id)
        
        # 验证权限：只能删除自己的客户端
        if mapping.user_id != current_user.id:
            return jsonify({
                'success': False,
                'message': '没有权限删除此客户端'
            }), 403
        
        # 检查是否为第一个客户端（不允许删除）
        user_mappings = ClientMapping.query.filter_by(user_id=current_user.id).order_by(ClientMapping.created_at).all()
        if user_mappings and user_mappings[0].id == mapping_id:
            return jsonify({
                'success': False,
                'message': '不能删除主客户端'
            }), 400
        
        client_name = mapping.client_name
        client_ids = mapping.client_ids
        
        # 初始化AdGuard服务
        adguard = AdGuardService()
        
        try:
            # 从AdGuard Home删除客户端
            adguard.delete_client(client_name)
            logging.info(f"已从AdGuard Home删除客户端: {client_name}")
        except Exception as e:
            logging.warning(f"从AdGuard Home删除客户端失败: {str(e)}")
            # 继续执行，不影响数据库删除
        
        try:
            # 从允许列表中移除客户端ID
            access_list = adguard._make_request('GET', '/access/list')
            allowed_clients = access_list.get('allowed_clients', [])
            
            # 移除客户端ID
            clients_to_remove = []
            for client_id in client_ids:
                if client_id in allowed_clients:
                    allowed_clients.remove(client_id)
                    clients_to_remove.append(client_id)
            
            # 如果有客户端ID被移除，更新访问控制列表
            if clients_to_remove:
                access_data = {
                    'allowed_clients': allowed_clients,
                    'disallowed_clients': access_list.get('disallowed_clients', []),
                    'blocked_hosts': access_list.get('blocked_hosts', [])
                }
                adguard._make_request('POST', '/access/set', json=access_data)
                logging.info(f"已从允许列表中移除客户端ID: {clients_to_remove}")
        except Exception as e:
            logging.warning(f"从允许列表移除客户端ID失败: {str(e)}")
            # 继续执行，不影响数据库删除
        
        # 删除数据库记录
        db.session.delete(mapping)
        
        # 记录操作日志
        operation_log = OperationLog(
            user_id=current_user.id,
            operation_type='DELETE',
            target_type='CLIENT',
            target_id=client_name,
            details=f'VIP用户删除客户端: {client_name}'
        )
        db.session.add(operation_log)
        db.session.commit()
        
        logging.info(f"VIP用户 {current_user.username} 成功删除客户端: {client_name}")
        
        return jsonify({
            'success': True,
            'message': '客户端删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"VIP用户删除客户端API错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500