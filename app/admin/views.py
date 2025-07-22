import logging
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog
from app.models.domain_config import DomainConfig
from app.models.domain_mapping import DomainMapping
from app.services.adguard_service import AdGuardService
from app.services.domain_service import DomainService
from . import admin
from functools import wraps

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
    from app.models.adguard_config import AdGuardConfig
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
            return jsonify({'message': '域名映射删除成功'})
        else:
            return jsonify({'error': '删除阿里云域名解析记录失败'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'删除域名映射失败：{str(e)}'}), 500

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