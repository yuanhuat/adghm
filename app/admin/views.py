import logging
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog
from app.models.domain_config import DomainConfig
from app.models.domain_mapping import DomainMapping
from app.models.feedback import Feedback
from app.models.email_config import EmailConfig
from app.models.adguard_config import AdGuardConfig
from app.models.query_log_analysis import QueryLogAnalysis, QueryLogExport
from app.services.adguard_service import AdGuardService
from app.services.domain_service import DomainService
from app.services.query_log_service import QueryLogService
from app.services.ai_analysis_service import AIAnalysisService
from . import admin
from functools import wraps
import os

def admin_required(f):
    """管理员权限装饰器
    
    确保只有管理员用户可以访问被装饰的视图函数。
    非管理员用户将被重定向到首页。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('您没有权限访问该页面', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/')
@login_required
@admin_required
def index():
    """管理员后台首页"""
    return render_template('admin/index.html')

@admin.route('/users')
@login_required
@admin_required
def users():
    """用户管理页面"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户
    
    同时删除用户关联的AdGuardHome客户端和映射记录
    """
    if user_id == current_user.id:
        return jsonify({'error': '不能删除当前登录的管理员账号'}), 400
        
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({'error': '不能删除其他管理员账号'}), 400
        
    try:
        # 删除用户的AdGuardHome客户端
        adguard = AdGuardService()
        client_delete_errors = []
        
        # 先删除AdGuardHome客户端，记录错误但继续执行
        for mapping in user.client_mappings:
            try:
                adguard.delete_client(mapping.client_name)
            except Exception as e:
                client_delete_errors.append(f"客户端 {mapping.client_name} 删除失败：{str(e)}")
        
        # 删除所有关联的域名映射记录
        domain_service = DomainService()
        domain_mappings = DomainMapping.query.filter_by(user_id=user.id).all()
        for domain_mapping in domain_mappings:
            try:
                # 记录删除的域名信息
                details = f'删除用户域名映射：{domain_mapping.full_domain}'
                if domain_mapping.ipv6_record_id:
                    details += f'（IPv4: {domain_mapping.ip_address}, IPv6: {domain_mapping.ipv6_address}）'
                else:
                    details += f'（IPv4: {domain_mapping.ip_address}）'
                    
                # 记录操作日志
                log = OperationLog(
                    user_id=current_user.id,
                    operation_type='delete',
                    target_type='domain_mapping',
                    target_id=str(domain_mapping.id),
                    details=details
                )
                db.session.add(log)
                
                # 尝试删除阿里云IPv4域名解析记录
                domain_service.delete_domain_record(domain_mapping.record_id)
                
                # 尝试删除阿里云IPv6域名解析记录（如果存在）
                if domain_mapping.ipv6_record_id:
                    domain_service.delete_domain_record(domain_mapping.ipv6_record_id)
            except Exception as e:
                logging.error(f"删除域名解析记录失败：{str(e)}")
            # 删除数据库中的域名映射记录
            db.session.delete(domain_mapping)
            
        # 删除所有关联的客户端映射记录
        for mapping in user.client_mappings:
            db.session.delete(mapping)
            
        # 删除用户记录
        db.session.delete(user)
        db.session.commit()
        
        # 如果有客户端删除失败，返回警告信息
        if client_delete_errors:
            return jsonify({
                'message': '用户删除成功，但部分客户端删除失败',
                'errors': client_delete_errors
            })
            
        return jsonify({'message': '用户删除成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'删除用户失败：{str(e)}'}), 500

@admin.route('/users/<int:user_id>/clients')
@login_required
@admin_required
def user_clients(user_id):
    """查看用户的客户端列表"""
    user = User.query.get_or_404(user_id)
    return render_template('admin/user_clients.html', user=user)

@admin.route('/users/<int:user_id>/clients/<int:mapping_id>', methods=['PUT'])
@login_required
@admin_required
def update_client(user_id, mapping_id):
    """更新用户的客户端配置"""
    user = User.query.get_or_404(user_id)
    mapping = ClientMapping.query.get_or_404(mapping_id)
    
    if mapping.user_id != user.id:
        return jsonify({'error': '客户端映射关系不匹配'}), 400
        
    data = request.get_json()
    client_ids = data.get('client_ids', [])
    
    try:
        # 更新AdGuardHome客户端
        adguard = AdGuardService()
        adguard.update_client(
            name=mapping.client_name,
            ids=client_ids
        )
        
        # 更新映射记录
        mapping.client_ids = client_ids
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='update_client',
            target_type='client',
            target_id=mapping.client_name,
            details=f'更新用户{user.username}的客户端{mapping.client_name}配置'
        )
        db.session.add(log)
        
        db.session.commit()
        return jsonify({'message': '客户端更新成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新客户端失败：{str(e)}'}), 500

@admin.route('/logs')
@login_required
@admin_required
def operation_logs():
    """操作日志页面"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    logs = OperationLog.query.order_by(
        OperationLog.created_at.desc()
    ).paginate(page=page, per_page=per_page)
    
    return render_template('admin/logs.html', logs=logs)

@admin.route('/adguard-config')
@login_required
@admin_required
def adguard_config():
    """AdGuardHome配置页面"""
    config = AdGuardConfig.get_config()
    return render_template('admin/adguard_config.html', config=config)

@admin.route('/adguard-config', methods=['POST'])
@login_required
@admin_required
def update_adguard_config():
    """更新AdGuardHome配置"""
    from app.models.adguard_config import AdGuardConfig
    
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400
        
    api_base_url = data.get('api_base_url', '').strip()
    auth_username = data.get('auth_username', '').strip()
    auth_password = data.get('auth_password', '').strip()
    
    # 获取并更新配置
    config = AdGuardConfig.get_config()
    config.api_base_url = api_base_url
    config.auth_username = auth_username
    config.auth_password = auth_password
    
    # 验证配置
    is_valid, error_msg = config.validate()
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    try:
        # 验证连接
        adguard = AdGuardService(config)
        status = adguard.get_status()
        if not status:
            return jsonify({'error': '无法连接到AdGuardHome服务器，请检查URL、端口和认证信息是否正确'}), 400
            
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='update_config',
            target_type='adguard_config',
            target_id='1',
            details=f'更新AdGuardHome配置：{api_base_url}'
        )
        db.session.add(log)
        
        db.session.commit()
        return jsonify({
            'message': '配置更新成功',
            'status': {
                'version': status.get('version', 'unknown'),
                'dns_addresses': status.get('dns_addresses', [])
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新配置失败：{str(e)}'}), 500

@admin.route('/query-log')
@login_required
@admin_required
def query_log():
    """查询 AdGuardHome 的日志
    
    实现分页功能，每页显示50条记录
    """
    adguard_service = AdGuardService()
    page = request.args.get('page', 1, type=int)
    older_than = request.args.get('older_than')
    
    # 每页显示50条记录
    per_page = 50
    
    try:
        # 获取日志数据，限制为每页记录数
        logs_data = adguard_service.get_query_log(older_than=older_than, limit=per_page)
        logs = logs_data.get('data', [])
        
        # 计算分页信息
        total_logs = len(logs)
        has_next = total_logs == per_page  # 如果返回的记录数等于限制数，说明可能还有更多记录
        
        # 获取下一页的older_than参数
        next_older_than = None
        if has_next and logs:
            next_older_than = logs[-1].get('time')
        
        # 获取上一页的older_than参数（这里简化处理，实际应该维护一个页面历史）
        prev_older_than = request.args.get('prev_older_than')
        
        print(f"传递给模板的日志数据: {logs[:5]}") # 打印前5条日志以供调试
        
        return render_template('admin/query_log.html', 
                             logs=logs, 
                             page=page,
                             has_next=has_next,
                             has_prev=page > 1,
                             next_older_than=next_older_than,
                             prev_older_than=prev_older_than,
                             per_page=per_page)
    except Exception as e:
        flash(f'获取查询日志失败: {str(e)}', 'error')
        return render_template('admin/query_log.html', 
                             logs=[], 
                             page=1,
                             has_next=False,
                             has_prev=False,
                             next_older_than=None,
                             prev_older_than=None,
                             per_page=per_page)

@admin.route('/query-log-enhanced')
@login_required
@admin_required
def query_log_enhanced():
    """增强查询日志页面"""
    return render_template('admin/query_log_enhanced.html')

@admin.route('/query-log/api')
@login_required
@admin_required
def query_log_api():
    """查询 AdGuardHome 日志的 API 接口
    
    返回 JSON 格式的日志数据，用于 AJAX 刷新
    """
    adguard_service = AdGuardService()
    page = request.args.get('page', 1, type=int)
    older_than = request.args.get('older_than')
    
    # 每页显示50条记录
    per_page = 50
    
    try:
        # 获取日志数据，限制为每页记录数
        logs_data = adguard_service.get_query_log(older_than=older_than, limit=per_page)
        logs = logs_data.get('data', [])
        
        # 计算分页信息
        total_logs = len(logs)
        has_next = total_logs == per_page  # 如果返回的记录数等于限制数，说明可能还有更多记录
        
        # 获取下一页的older_than参数
        next_older_than = None
        if has_next and logs:
            next_older_than = logs[-1].get('time')
        
        # 获取上一页的older_than参数
        prev_older_than = request.args.get('prev_older_than')
        
        return jsonify({
            'success': True,
            'logs': logs,
            'page': page,
            'has_next': has_next,
            'has_prev': page > 1,
            'next_older_than': next_older_than,
            'prev_older_than': prev_older_than,
            'per_page': per_page
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': [],
            'page': 1,
            'has_next': False,
            'has_prev': False,
            'next_older_than': None,
            'prev_older_than': None,
            'per_page': per_page
        }), 500

@admin.route('/adguard-status')
@login_required
@admin_required
def get_adguard_status():
    """获取AdGuardHome状态信息"""
    try:
        adguard = AdGuardService()
        if not adguard.check_connection():
            return jsonify({'error': '无法连接到AdGuardHome服务器，请检查配置是否正确'}), 503
            
        status = adguard.get_status()
        if not status:
            return jsonify({'error': '获取服务器状态失败'}), 500
            
        return jsonify({
            'status': 'ok',
            'version': status.get('version', 'unknown'),
            'dns_addresses': status.get('dns_addresses', []),
            'language': status.get('language', 'en'),
            'dns_port': status.get('dns_port', 53),
            'http_port': status.get('http_port', 80),
            'protection_enabled': status.get('protection_enabled', False),
            'running': status.get('running', False),
            'dhcp_available': status.get('dhcp_available', False)
        })
    except Exception as e:
        return jsonify({'error': f'获取状态失败：{str(e)}'}), 500

@admin.route('/domain-config')
@login_required
@admin_required
def domain_config():
    """阿里云域名解析配置页面"""
    config = DomainConfig.get_config()
    return render_template('admin/domain_config.html', config=config)

@admin.route('/domain-config', methods=['POST'])
@login_required
@admin_required
def update_domain_config():
    """更新阿里云域名解析配置"""
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400
        
    access_key_id = data.get('access_key_id', '').strip()
    access_key_secret = data.get('access_key_secret', '').strip()
    domain_name = data.get('domain_name', '').strip()
    
    # 获取并更新配置
    config = DomainConfig.get_config()
    config.access_key_id = access_key_id
    config.access_key_secret = access_key_secret
    config.domain_name = domain_name
    
    # 验证配置
    is_valid, error_msg = config.validate()
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    try:
        # 验证阿里云API连接
        domain_service = DomainService()
        if not domain_service.check_connection():
            return jsonify({'error': '无法连接到阿里云API，请检查AccessKey和域名信息是否正确'}), 400
            
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='update_config',
            target_type='domain_config',
            target_id='1',
            details=f'更新阿里云域名解析配置：{domain_name}'
        )
        db.session.add(log)
        
        db.session.commit()
        return jsonify({
            'message': '配置更新成功',
            'domain': domain_name
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新配置失败：{str(e)}'}), 500

@admin.route('/domain-mappings')
@login_required
@admin_required
def domain_mappings():
    """域名映射管理页面"""
    mappings = DomainMapping.query.all()
    return render_template('admin/domain_mappings.html', mappings=mappings)

@admin.route('/domain-mappings/<int:mapping_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_domain_mapping(mapping_id):
    """删除域名映射"""
    mapping = DomainMapping.query.get_or_404(mapping_id)
    
    try:
        # 删除阿里云域名解析记录
        domain_service = DomainService()
        success = domain_service.delete_domain_record(mapping.record_id)
        
        # 如果存在IPv6记录，也删除它
        ipv6_success = True
        if mapping.ipv6_record_id:
            ipv6_success = domain_service.delete_domain_record(mapping.ipv6_record_id)
        
        if success and ipv6_success:
            # 记录操作日志
            details = f'删除域名映射：{mapping.full_domain}'
            if mapping.ipv6_record_id:
                details += f'（IPv4: {mapping.ip_address}, IPv6: {mapping.ipv6_address}）'
            else:
                details += f'（IPv4: {mapping.ip_address}）'
                
            log = OperationLog(
                user_id=current_user.id,
                operation_type='delete',
                target_type='domain_mapping',
                target_id=str(mapping.id),
                details=details
            )
            db.session.add(log)
            
            # 删除映射记录
            db.session.delete(mapping)
            db.session.commit()
            
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': '删除域名解析记录失败'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)})

@admin.route('/access-control')
@login_required
@admin_required
def access_control():
    """访问控制列表管理页面
    
    显示当前的访问控制列表配置，包括允许的客户端和拒绝的客户端
    """
    try:
        # 获取当前的访问控制列表
        adguard = AdGuardService()
        access_list = adguard.get_access_list()
        
        # 获取所有用户的客户端映射，用于显示客户端名称
        client_mappings = ClientMapping.query.all()
        client_id_to_name = {}
        client_id_to_user = {}
        
        for mapping in client_mappings:
            user = User.query.get(mapping.user_id)
            if user:
                for client_id in mapping.client_ids:
                    client_id_to_name[client_id] = mapping.client_name
                    client_id_to_user[client_id] = user.username
        
        # 处理允许和拒绝列表，添加客户端名称和用户信息
        allowed_clients = []
        for client_id in access_list.get('allowed_clients', []):
            client_info = {
                'id': client_id,
                'name': client_id_to_name.get(client_id, '未知客户端'),
                'user': client_id_to_user.get(client_id, '未知用户')
            }
            allowed_clients.append(client_info)
            
        disallowed_clients = []
        for client_id in access_list.get('disallowed_clients', []):
            client_info = {
                'id': client_id,
                'name': client_id_to_name.get(client_id, '未知客户端'),
                'user': client_id_to_user.get(client_id, '未知用户')
            }
            disallowed_clients.append(client_info)
        
        # 获取所有用户的客户端，用于添加到列表
        all_clients = []
        for mapping in client_mappings:
            user = User.query.get(mapping.user_id)
            if user:
                for client_id in mapping.client_ids:
                    # 检查是否已在允许或拒绝列表中
                    if client_id not in [c['id'] for c in allowed_clients] and \
                       client_id not in [c['id'] for c in disallowed_clients]:
                        client_info = {
                            'id': client_id,
                            'name': mapping.client_name,
                            'user': user.username
                        }
                        all_clients.append(client_info)
        
        return render_template(
            'admin/access_control.html',
            allowed_clients=allowed_clients,
            disallowed_clients=disallowed_clients,
            all_clients=all_clients,
            blocked_hosts=access_list.get('blocked_hosts', [])
        )
    except Exception as e:
        flash(f'获取访问控制列表失败: {str(e)}', 'error')
        return render_template(
            'admin/access_control.html',
            allowed_clients=[],
            disallowed_clients=[],
            all_clients=[],
            blocked_hosts=[]
        )

@admin.route('/access-control/update', methods=['POST'])
@login_required
@admin_required
def update_access_control():
    """更新访问控制列表
    
    处理访问控制列表的更新请求，包括添加或删除允许/拒绝的客户端
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': '请求数据不能为空'}), 400
        
    action = data.get('action')
    client_id = data.get('client_id')
    list_type = data.get('list_type')  # 'allowed' 或 'disallowed'
    
    if not action or not client_id or not list_type:
        return jsonify({'error': '缺少必要参数'}), 400
        
    if list_type not in ['allowed', 'disallowed']:
        return jsonify({'error': '无效的列表类型'}), 400
        
    if action not in ['add', 'remove']:
        return jsonify({'error': '无效的操作类型'}), 400
    
    try:
        # 获取当前的访问控制列表
        adguard = AdGuardService()
        access_list = adguard.get_access_list()
        
        allowed_clients = access_list.get('allowed_clients', [])
        disallowed_clients = access_list.get('disallowed_clients', [])
        blocked_hosts = access_list.get('blocked_hosts', [])
        
        # 根据操作类型和列表类型更新列表
        if action == 'add':
            if list_type == 'allowed':
                # 添加到允许列表前，确保不在拒绝列表中
                if client_id in disallowed_clients:
                    disallowed_clients.remove(client_id)
                # 添加到允许列表（如果不存在）
                if client_id not in allowed_clients:
                    allowed_clients.append(client_id)
            else:  # disallowed
                # 添加到拒绝列表前，确保不在允许列表中
                if client_id in allowed_clients:
                    allowed_clients.remove(client_id)
                # 添加到拒绝列表（如果不存在）
                if client_id not in disallowed_clients:
                    disallowed_clients.append(client_id)
        else:  # remove
            if list_type == 'allowed' and client_id in allowed_clients:
                allowed_clients.remove(client_id)
            elif list_type == 'disallowed' and client_id in disallowed_clients:
                disallowed_clients.remove(client_id)
        
        # 更新访问控制列表
        result = adguard.set_access_list(
            allowed_clients=allowed_clients,
            disallowed_clients=disallowed_clients,
            blocked_hosts=blocked_hosts
        )
        
        # 记录操作日志
        action_text = '添加' if action == 'add' else '移除'
        list_text = '允许列表' if list_type == 'allowed' else '拒绝列表'
        
        # 获取客户端名称和用户信息
        # 由于client_ids是一个property，不能直接使用contains方法
        # 需要查找所有客户端映射，然后在Python中过滤
        client_mappings = ClientMapping.query.all()
        client_mapping = next((cm for cm in client_mappings if client_id in cm.client_ids), None)
        
        client_name = '未知客户端'
        user_info = '未知用户'
        
        if client_mapping:
            client_name = client_mapping.client_name
            user = User.query.get(client_mapping.user_id)
            if user:
                user_info = user.username
        
        details = f'{action_text}客户端到{list_text}：{client_id}（{client_name}，用户：{user_info}）'
        
        log = OperationLog(
            user_id=current_user.id,
            operation_type=f'{action}_{list_type}_client',
            target_type='access_control',
            target_id='1',
            details=details
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功{action_text}客户端到{list_text}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'更新访问控制列表失败：{str(e)}'}), 500

@admin.route('/domain-mappings/<int:mapping_id>/refresh', methods=['POST'])
@login_required
@admin_required
def refresh_domain_mapping(mapping_id):
    """刷新域名映射的IP地址"""
    mapping = DomainMapping.query.get_or_404(mapping_id)
    
    try:
        # 获取最新IP地址
        domain_service = DomainService()
        ip_address = domain_service.get_ip_address()
        
        if not ip_address:
            return jsonify({'error': '无法获取当前IP地址'}), 500
            
        # 更新阿里云域名解析记录
        success, record_id, _ = domain_service.create_or_update_subdomain(
            subdomain=mapping.subdomain,
            ip_address=ip_address,
            record_id=mapping.record_id
        )
        
        if success:
            # 更新映射记录
            old_ip = mapping.ip_address
            mapping.ip_address = ip_address
            if record_id and record_id != mapping.record_id:
                mapping.record_id = record_id
                
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update',
                target_type='domain_mapping',
                target_id=str(mapping.id),
                details=f'刷新域名映射IP地址：{mapping.full_domain}，从 {old_ip} 更新为 {ip_address}'
            )
            db.session.add(log)
            
            db.session.commit()
            return jsonify({
                'message': '域名映射IP地址刷新成功',
                'ip_address': ip_address
            })
        else:
            return jsonify({'error': '更新阿里云域名解析记录失败'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'刷新域名映射IP地址失败：{str(e)}'}), 500

@admin.route('/blocked-services')
@login_required
@admin_required
def blocked_services():
    """全局阻止服务配置页面"""
    return render_template('admin/blocked_services.html')


@admin.route('/feedbacks')
@login_required
@admin_required
def feedbacks():
    """留言管理页面
    
    显示所有用户的留言列表，支持分页和状态筛选
    """
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')
    per_page = 20
    
    # 构建查询
    query = Feedback.query
    
    if status != 'all':
        query = query.filter_by(status=status)
    
    # 按创建时间倒序排列并分页
    feedbacks = query.order_by(Feedback.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/feedbacks.html', feedbacks=feedbacks, current_status=status)


@admin.route('/api/feedbacks')
@login_required
@admin_required
def api_feedbacks():
    """获取留言列表API接口
    
    支持分页和状态筛选
    
    Returns:
        JSON: 留言列表数据
    """
    try:
        page = request.args.get('page', 1, type=int)
        status = request.args.get('status', 'all')
        per_page = 20
        
        # 构建查询
        query = Feedback.query
        
        if status != 'all':
            query = query.filter_by(status=status)
        
        # 按创建时间倒序排列并分页
        feedbacks_pagination = query.order_by(Feedback.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        feedback_list = []
        for feedback in feedbacks_pagination.items:
            feedback_dict = feedback.to_dict()
            feedback_dict['user_name'] = feedback_dict.get('username', '未知用户')
            feedback_list.append(feedback_dict)
        
        # 获取统计信息
        total_count = Feedback.query.count()
        open_count = Feedback.query.filter_by(status='open').count()
        closed_count = Feedback.query.filter_by(status='closed').count()
        
        return jsonify({
            'success': True,
            'feedbacks': feedback_list,
            'pagination': {
                'page': page,
                'pages': feedbacks_pagination.pages,
                'per_page': per_page,
                'total': feedbacks_pagination.total,
                'has_prev': feedbacks_pagination.has_prev,
                'has_next': feedbacks_pagination.has_next,
                'prev_num': feedbacks_pagination.prev_num,
                'next_num': feedbacks_pagination.next_num
            },
            'stats': {
                'total': total_count,
                'open': open_count,
                'closed': closed_count
            }
        })
    except Exception as e:
        logging.error(f"获取留言列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'获取留言列表失败: {str(e)}'
        }), 500


@admin.route('/api/feedbacks/<int:feedback_id>/close', methods=['POST'])
@login_required
@admin_required
def close_feedback(feedback_id):
    """关闭留言API接口
    
    Args:
        feedback_id: 留言ID
    
    Returns:
        JSON: 操作结果
    """
    try:
        feedback = Feedback.query.get_or_404(feedback_id)
        
        if feedback.status == 'closed':
            return jsonify({
                'success': False,
                'error': '留言已经关闭'
            }), 400
        
        data = request.get_json()
        admin_reply = data.get('reply', '').strip() if data else ''
        
        # 关闭留言
        feedback.close_feedback(current_user.id, admin_reply)
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='close_feedback',
            target_type='feedback',
            target_id=str(feedback.id),
            details=f'关闭留言: {feedback.title}' + (f'，回复: {admin_reply}' if admin_reply else '')
        )
        db.session.add(log)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '留言已关闭',
            'feedback': feedback.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"关闭留言失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'关闭留言失败: {str(e)}'
        }), 500


@admin.route('/api/feedbacks/<int:feedback_id>/reply', methods=['POST'])
@login_required
@admin_required
def reply_feedback(feedback_id):
    """回复留言API接口
    
    Args:
        feedback_id: 留言ID
    
    Returns:
        JSON: 操作结果
    """
    try:
        feedback = Feedback.query.get_or_404(feedback_id)
        
        data = request.get_json()
        admin_reply = data.get('reply', '').strip()
        
        if not admin_reply:
            return jsonify({
                'success': False,
                'error': '回复内容不能为空'
            }), 400
        
        if len(admin_reply) > 2000:
            return jsonify({
                'success': False,
                'error': '回复内容不能超过2000个字符'
            }), 400
        
        # 更新回复内容
        feedback.admin_reply = admin_reply
        feedback.updated_at = datetime.utcnow()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='reply_feedback',
            target_type='feedback',
            target_id=str(feedback.id),
            details=f'回复留言: {feedback.title}，回复内容: {admin_reply}'
        )
        db.session.add(log)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '回复成功',
            'feedback': feedback.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"回复留言失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'回复留言失败: {str(e)}'
        }), 500


@admin.route('/email-config')
@login_required
@admin_required
def email_config():
    """邮箱配置页面
    
    显示当前邮箱配置信息，允许管理员修改邮件服务器设置
    """
    # 从数据库读取当前邮箱配置
    email_config_obj = EmailConfig.get_config()
    config = email_config_obj.to_dict()
    return render_template('admin/email_config.html', config=config)


@admin.route('/email-config', methods=['POST'])
@login_required
@admin_required
def update_email_config():
    """更新邮箱配置
    
    接收表单数据并更新数据库中的邮箱配置
    """
    try:
        # 获取表单数据
        form_data = {
            'mail_server': request.form.get('mail_server', '').strip(),
            'mail_port': request.form.get('mail_port', '587').strip(),
            'mail_use_tls': request.form.get('mail_use_tls', 'false'),
            'mail_username': request.form.get('mail_username', '').strip(),
            'mail_password': request.form.get('mail_password', '').strip(),
            'mail_default_sender': request.form.get('mail_default_sender', '').strip(),
            'verification_code_expire_minutes': request.form.get('verification_code_expire_minutes', '10').strip()
        }
        
        # 获取当前配置
        email_config_obj = EmailConfig.get_config()
        
        # 更新配置
        email_config_obj.update_from_dict(form_data)
        
        # 验证配置
        is_valid, error_msg = email_config_obj.validate()
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('admin.email_config'))
        
        # 保存到数据库
        db.session.commit()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='update_email_config',
            target_type='system',
            target_id='email_config',
            details=f'更新邮箱配置: 服务器={email_config_obj.mail_server}, 端口={email_config_obj.mail_port}, 用户名={email_config_obj.mail_username}'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('邮箱配置更新成功', 'success')
        return redirect(url_for('admin.email_config'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"更新邮箱配置失败: {str(e)}")
        flash(f'更新邮箱配置失败: {str(e)}', 'error')
        return redirect(url_for('admin.email_config'))


@admin.route('/test-email-config', methods=['POST'])
@login_required
@admin_required
def test_email_config():
    """测试邮箱配置
    
    使用提供的配置参数发送测试邮件
    """
    try:
        # 获取表单数据
        mail_server = request.form.get('mail_server', '').strip()
        mail_port = request.form.get('mail_port', '587').strip()
        mail_use_tls = request.form.get('mail_use_tls', 'false') == 'true'
        mail_username = request.form.get('mail_username', '').strip()
        mail_password = request.form.get('mail_password', '').strip()
        mail_default_sender = request.form.get('mail_default_sender', '').strip()
        
        # 验证必填字段
        if not all([mail_server, mail_port, mail_username, mail_default_sender]):
            return jsonify({
                'success': False,
                'error': '请填写所有必填字段'
            })
        
        # 如果没有提供密码，使用数据库中的密码
        if not mail_password:
            email_config_obj = EmailConfig.get_config()
            mail_password = email_config_obj.mail_password
            if not mail_password:
                return jsonify({
                    'success': False,
                    'error': '请提供邮箱密码或确保数据库中已配置密码'
                })
        
        # 验证端口号
        try:
            port_num = int(mail_port)
            if port_num < 1 or port_num > 65535:
                raise ValueError()
        except ValueError:
            return jsonify({
                'success': False,
                'error': '邮件服务器端口必须是1-65535之间的数字'
            })
        
        # 创建临时的邮件配置进行测试
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # 创建邮件内容
        msg = MIMEMultipart()
        msg['From'] = mail_default_sender
        msg['To'] = mail_username  # 发送给自己进行测试
        msg['Subject'] = '[AdGuardHome管理系统] 邮箱配置测试'
        
        body = f"""
        这是一封测试邮件，用于验证邮箱配置是否正确。
        
        配置信息：
        - 邮件服务器：{mail_server}
        - 端口：{mail_port}
        - TLS加密：{'是' if mail_use_tls else '否'}
        - 发件人：{mail_default_sender}
        
        如果您收到这封邮件，说明邮箱配置正确。
        
        发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 连接SMTP服务器并发送邮件
        server = smtplib.SMTP(mail_server, port_num)
        
        if mail_use_tls:
            server.starttls()
        
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='test_email_config',
            target_type='system',
            target_id='email_config',
            details=f'测试邮箱配置: 服务器={mail_server}, 端口={mail_port}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'测试邮件已发送到 {mail_username}，请检查收件箱'
        })
        
    except smtplib.SMTPAuthenticationError:
        return jsonify({
            'success': False,
            'error': 'SMTP认证失败，请检查用户名和密码是否正确'
        })
    except smtplib.SMTPConnectError:
        return jsonify({
            'success': False,
            'error': f'无法连接到邮件服务器 {mail_server}:{mail_port}，请检查服务器地址和端口'
        })
    except smtplib.SMTPException as e:
        return jsonify({
            'success': False,
            'error': f'SMTP错误: {str(e)}'
        })
    except Exception as e:
        logging.error(f"测试邮箱配置失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'测试失败: {str(e)}'
        })


@admin.route('/query-log-analysis')
@login_required
@admin_required
def query_log_analysis():
    """查询日志分析页面"""
    return render_template('admin/query_log_analysis.html')


@admin.route('/api/query-log-analysis/start', methods=['POST'])
@login_required
@admin_required
def start_query_log_analysis():
    """启动查询日志分析任务"""
    try:
        data = request.get_json()
        analysis_type = data.get('analysis_type', 'basic')
        time_range = data.get('time_range', '1h')
        
        # 创建分析任务
        analysis = QueryLogAnalysis(
            user_id=current_user.id,
            analysis_type=analysis_type,
            time_range=time_range,
            status='pending'
        )
        db.session.add(analysis)
        db.session.flush()  # 获取ID
        
        # 启动后台分析任务
        query_log_service = QueryLogService()
        query_log_service.start_analysis_task(analysis.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'analysis_id': analysis.id,
            'message': '分析任务已启动'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
             'success': False,
             'error': str(e)
         }), 500


@admin.route('/api/query-log/advanced-search', methods=['POST'])
@login_required
@admin_required
def advanced_search_query_log():
    """高级搜索查询日志"""
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        page_size = data.get('page_size', 50)
        older_than = data.get('older_than')
        
        query_log_service = QueryLogService()
        result = query_log_service.advanced_search(
            filters=filters,
            page_size=page_size,
            older_than=older_than
        )
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/query-log/export', methods=['POST'])
@login_required
@admin_required
def export_query_log():
    """导出查询日志"""
    try:
        data = request.get_json()
        export_format = data.get('format', 'csv')
        filters = data.get('filters', {})
        max_records = data.get('max_records', 10000)
        
        query_log_service = QueryLogService()
        file_path = query_log_service.export_logs(
            export_format=export_format,
            filters=filters,
            max_records=max_records,
            user_id=current_user.id
        )
        
        if file_path:
            return jsonify({
                'success': True,
                'file_path': file_path,
                'message': '导出成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '导出失败'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/query-log/analysis-report', methods=['POST'])
@login_required
@admin_required
def generate_analysis_report():
    """生成DNS查询趋势分析报告"""
    try:
        data = request.get_json()
        time_range = data.get('time_range', '24h')
        
        query_log_service = QueryLogService()
        report = query_log_service.generate_analysis_report(time_range=time_range)
        
        return jsonify({
            'success': True,
            'report': report
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/ai-analysis/domain', methods=['POST'])
@login_required
@admin_required
def analyze_domain_with_ai():
    """使用AI分析域名"""
    try:
        data = request.get_json()
        domain = data.get('domain')
        
        if not domain:
            return jsonify({
                'success': False,
                'error': '域名不能为空'
            }), 400
        
        ai_service = AIAnalysisService()
        result = ai_service.analyze_domain(domain)
        
        if result:
            return jsonify({
                'success': True,
                'analysis': result
            })
        else:
            return jsonify({
                'success': False,
                'error': 'AI分析失败，请检查API配置'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/ai-analysis/domains/batch', methods=['POST'])
@login_required
@admin_required
def analyze_domains_batch():
    """批量分析域名"""
    try:
        data = request.get_json()
        domains = data.get('domains', [])
        
        if not domains:
            return jsonify({
                'success': False,
                'error': '域名列表不能为空'
            }), 400
        
        ai_service = AIAnalysisService()
        results = ai_service.analyze_domains_batch(domains)
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/ai-analysis/pending-reviews')
@login_required
@admin_required
def get_pending_reviews():
    """获取待审核的AI分析结果"""
    try:
        ai_service = AIAnalysisService()
        pending_reviews = ai_service.get_pending_reviews()
        
        return jsonify({
            'success': True,
            'reviews': [review.to_dict() for review in pending_reviews]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/ai-analysis/review', methods=['POST'])
@login_required
@admin_required
def review_ai_analysis():
    """审核AI分析结果"""
    try:
        data = request.get_json()
        analysis_id = data.get('analysis_id')
        admin_action = data.get('action')  # block, allow, ignore
        admin_notes = data.get('notes', '')
        
        if not analysis_id or not admin_action:
            return jsonify({
                'success': False,
                'error': '分析ID和操作不能为空'
            }), 400
        
        ai_service = AIAnalysisService()
        success = ai_service.review_analysis(
            analysis_id=analysis_id,
            admin_action=admin_action,
            admin_notes=admin_notes,
            reviewer_id=current_user.id
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '审核完成'
            })
        else:
            return jsonify({
                'success': False,
                'error': '审核失败'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/ai-analysis/stats')
@login_required
@admin_required
def get_ai_analysis_stats():
    """获取AI分析统计信息"""
    try:
        ai_service = AIAnalysisService()
        stats = ai_service.get_analysis_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/ai-analysis-config')
@login_required
@admin_required
def ai_analysis_config():
    """AI分析配置页面"""
    return render_template('admin/ai_analysis_config.html')


@admin.route('/api/ai-analysis/config', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_ai_analysis_config():
    """管理AI分析配置"""
    if request.method == 'GET':
        try:
            config = AdGuardConfig.get_config()
            return jsonify({
                'success': True,
                'config': {
                    'deepseek_api_key': getattr(config, 'deepseek_api_key', ''),
                    'auto_analysis_enabled': getattr(config, 'auto_analysis_enabled', False),
                    'analysis_threshold': getattr(config, 'analysis_threshold', 0.8)
                }
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            config = AdGuardConfig.get_config()
            
            # 更新配置
            if 'deepseek_api_key' in data:
                config.deepseek_api_key = data['deepseek_api_key']
            if 'auto_analysis_enabled' in data:
                config.auto_analysis_enabled = data['auto_analysis_enabled']
            if 'analysis_threshold' in data:
                config.analysis_threshold = float(data['analysis_threshold'])
            
            db.session.commit()
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_ai_config',
                target_type='config',
                target_id='ai_analysis',
                details='更新AI分析配置'
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'AI分析配置已更新'
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@admin.route('/api/query-log-analysis/<int:analysis_id>/status')
@login_required
@admin_required
def get_analysis_status(analysis_id):
    """获取分析任务状态"""
    try:
        analysis = QueryLogAnalysis.query.get_or_404(analysis_id)
        return jsonify({
            'success': True,
            'analysis': analysis.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/query-log-analysis/<int:analysis_id>/result')
@login_required
@admin_required
def get_analysis_result(analysis_id):
    """获取分析结果"""
    try:
        analysis = QueryLogAnalysis.query.get_or_404(analysis_id)
        if analysis.status != 'completed':
            return jsonify({
                'success': False,
                'error': '分析尚未完成'
            }), 400
            
        return jsonify({
            'success': True,
            'result': analysis.result_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/query-log-analysis/export', methods=['POST'])
@login_required
@admin_required
def export_query_log_analysis():
    """导出查询日志分析结果"""
    try:
        data = request.get_json()
        analysis_id = data.get('analysis_id')
        export_format = data.get('format', 'json')
        
        analysis = QueryLogAnalysis.query.get_or_404(analysis_id)
        
        # 创建导出任务
        export_task = QueryLogExport(
            analysis_id=analysis_id,
            user_id=current_user.id,
            export_format=export_format,
            status='pending'
        )
        db.session.add(export_task)
        db.session.flush()
        
        # 启动导出任务
        query_log_service = QueryLogService()
        query_log_service.start_export_task(export_task.id)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'export_id': export_task.id,
            'message': '导出任务已启动'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/query-log-analysis/ai-insights', methods=['POST'])
@login_required
@admin_required
def get_ai_insights():
    """获取AI分析洞察"""
    try:
        data = request.get_json()
        analysis_id = data.get('analysis_id')
        
        analysis = QueryLogAnalysis.query.get_or_404(analysis_id)
        if analysis.status != 'completed':
            return jsonify({
                'success': False,
                'error': '分析尚未完成'
            }), 400
        
        # 使用AI服务生成洞察
        ai_service = AIAnalysisService()
        insights = ai_service.generate_insights(analysis.result_data)
        
        return jsonify({
            'success': True,
            'insights': insights
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500