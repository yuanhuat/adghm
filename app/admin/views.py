from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.utils.timezone import beijing_time
from app.models.user import User
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog
from app.models.announcement import Announcement
from app.models.dns_import_source import DnsImportSource

from app.models.feedback import Feedback
from app.models.email_config import EmailConfig
from app.models.adguard_config import AdGuardConfig
from app.models.dns_config import DnsConfig
from app.models.system_config import SystemConfig
from app.models.donation_config import DonationConfig
from app.models.donation_record import DonationRecord
from app.models.vip_config import VipConfig
from app.models.query_log_analysis import QueryLogAnalysis, QueryLogExport

from app.services.email_service import EmailService

from app.services.query_log_service import QueryLogService
from app.services.ai_analysis_service import AIAnalysisService
from app.services.adguard_service import AdGuardService
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
    
    # 获取每个用户的DNS请求数
    user_stats = {}
    try:
        adguard_service = AdGuardService()
        stats = adguard_service.get_stats()
        
        if stats and 'top_clients' in stats:
            for user in users:
                user_request_count = 0
                # 获取用户的客户端映射
                user_clients = ClientMapping.query.filter_by(user_id=user.id).all()
                user_client_names = [client.client_name for client in user_clients]
                user_client_ids = []
                for client in user_clients:
                    user_client_ids.extend(client.client_ids)
                
                # 在top_clients中查找用户的客户端请求数
                for client_stat in stats['top_clients']:
                    for client_name, request_count in client_stat.items():
                        if client_name in user_client_names or client_name in user_client_ids:
                            user_request_count += request_count
                
                user_stats[user.id] = user_request_count
    except Exception as e:
        print(f"获取用户DNS请求统计失败: {str(e)}")
        user_stats = {}
    
    return render_template('admin/users.html', users=users, user_stats=user_stats)

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
        
        # 从AdGuardHome的允许客户端列表中移除用户的客户端ID
        try:
            # 获取当前的访问控制列表
            access_list = adguard._make_request('GET', '/access/list')
            allowed_clients = access_list.get('allowed_clients', [])
            
            # 移除用户的所有客户端ID
            clients_to_remove = []
            for mapping in user.client_mappings:
                for client_id in mapping.client_ids:
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
                print(f"已从允许列表中移除客户端ID: {clients_to_remove}")
        except Exception as e:
            client_delete_errors.append(f"从允许列表移除客户端ID失败：{str(e)}")
            print(f"从允许列表移除客户端ID失败: {str(e)}")
        
        # 注意：域名映射功能已移除
        # 不再需要删除域名映射记录
            
        # 删除所有关联的客户端映射记录
        for mapping in user.client_mappings:
            db.session.delete(mapping)
        
        # 处理用户的反馈记录
        from app.models.feedback import Feedback
        # 查找用户的所有反馈
        feedbacks = Feedback.query.filter_by(user_id=user_id).all()
        for feedback in feedbacks:
            # 将反馈的用户ID设为NULL
            db.session.delete(feedback)
            
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

@admin.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_single_user(user_id):
    """删除单个用户
    
    删除指定用户及其关联的AdGuardHome客户端和映射记录
    """
    try:
        # 获取用户
        user = User.query.get_or_404(user_id)
        
        # 检查是否为当前用户或管理员
        if user.id == current_user.id:
            return jsonify({
                'success': False, 
                'message': f'用户{user.username}：不能删除当前登录的管理员账号'
            }), 400
        elif user.is_admin:
            return jsonify({
                'success': False, 
                'message': f'用户{user.username}：不能删除其他管理员账号'
            }), 400
        
        errors = []
        adguard = AdGuardService()
        
        # 删除用户的AdGuardHome客户端
        for mapping in user.client_mappings:
            try:
                adguard.delete_client(mapping.client_name)
            except Exception as e:
                errors.append(f"客户端 {mapping.client_name} 删除失败：{str(e)}")
        
        # 从AdGuardHome的允许客户端列表中移除用户的客户端ID
        try:
            access_list = adguard._make_request('GET', '/access/list')
            allowed_clients = access_list.get('allowed_clients', [])
            
            clients_to_remove = []
            for mapping in user.client_mappings:
                for client_id in mapping.client_ids:
                    if client_id in allowed_clients:
                        allowed_clients.remove(client_id)
                        clients_to_remove.append(client_id)
            
            if clients_to_remove:
                access_data = {
                    'allowed_clients': allowed_clients,
                    'disallowed_clients': access_list.get('disallowed_clients', []),
                    'blocked_hosts': access_list.get('blocked_hosts', [])
                }
                adguard._make_request('POST', '/access/set', json=access_data)
        except Exception as e:
            errors.append(f"从允许列表移除客户端ID失败：{str(e)}")
        
        # 删除所有关联的客户端映射记录
        for mapping in user.client_mappings:
            db.session.delete(mapping)
        
        # 处理用户的反馈记录
        from app.models.feedback import Feedback
        feedbacks = Feedback.query.filter_by(user_id=user.id).all()
        for feedback in feedbacks:
            db.session.delete(feedback)
        
        # 删除用户记录
        db.session.delete(user)
        db.session.commit()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='delete_user',
            target_type='User',
            target_id=str(user_id),
            details=f'删除用户：{user.username}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'用户{user.username}删除成功',
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'删除用户失败：{str(e)}'
        }), 500

@admin.route('/bulk-delete-users', methods=['POST'])
@login_required
@admin_required
def bulk_delete_users():
    """批量删除用户（逐个删除方式）
    
    逐个删除选中的用户，提供详细的删除进度和结果
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求数据格式错误'}), 400
        
        user_ids = data.get('user_ids', [])
        
        # 验证必填字段
        if not user_ids:
            return jsonify({'success': False, 'message': '请选择要删除的用户'}), 400
        
        # 获取选中的用户
        users = User.query.filter(User.id.in_(user_ids)).all()
        if not users:
            return jsonify({'success': False, 'message': '未找到选中的用户'}), 400
        
        # 检查是否包含当前用户或管理员
        invalid_users = []
        valid_users = []
        for user in users:
            if user.id == current_user.id:
                invalid_users.append(f'用户{user.username}：不能删除当前登录的管理员账号')
            elif user.is_admin:
                invalid_users.append(f'用户{user.username}：不能删除其他管理员账号')
            else:
                valid_users.append(user)
        
        if invalid_users and not valid_users:
            return jsonify({
                'success': False, 
                'message': '包含无法删除的用户：\n' + '\n'.join(invalid_users)
            }), 400
        
        # 初始化统计
        success_count = 0
        failed_count = 0
        errors = []
        results = []
        
        # 如果有无效用户，添加到错误列表
        if invalid_users:
            errors.extend(invalid_users)
            failed_count += len(invalid_users)
        
        adguard = AdGuardService()
        
        # 逐个删除用户
        for i, user in enumerate(valid_users, 1):
            user_result = {
                'username': user.username,
                'success': False,
                'errors': []
            }
            
            try:
                client_delete_errors = []
                
                # 删除用户的AdGuardHome客户端
                for mapping in user.client_mappings:
                    try:
                        adguard.delete_client(mapping.client_name)
                    except Exception as e:
                        client_delete_errors.append(f"客户端 {mapping.client_name} 删除失败：{str(e)}")
                
                # 从AdGuardHome的允许客户端列表中移除用户的客户端ID
                try:
                    access_list = adguard._make_request('GET', '/access/list')
                    allowed_clients = access_list.get('allowed_clients', [])
                    
                    clients_to_remove = []
                    for mapping in user.client_mappings:
                        for client_id in mapping.client_ids:
                            if client_id in allowed_clients:
                                allowed_clients.remove(client_id)
                                clients_to_remove.append(client_id)
                    
                    if clients_to_remove:
                        access_data = {
                            'allowed_clients': allowed_clients,
                            'disallowed_clients': access_list.get('disallowed_clients', []),
                            'blocked_hosts': access_list.get('blocked_hosts', [])
                        }
                        adguard._make_request('POST', '/access/set', json=access_data)
                except Exception as e:
                    client_delete_errors.append(f"从允许列表移除客户端ID失败：{str(e)}")
                
                # 删除所有关联的客户端映射记录
                for mapping in user.client_mappings:
                    db.session.delete(mapping)
                
                # 处理用户的反馈记录
                from app.models.feedback import Feedback
                feedbacks = Feedback.query.filter_by(user_id=user.id).all()
                for feedback in feedbacks:
                    db.session.delete(feedback)
                
                # 删除用户记录
                db.session.delete(user)
                db.session.commit()  # 每个用户单独提交
                
                success_count += 1
                user_result['success'] = True
                
                # 如果有客户端删除失败，记录警告
                if client_delete_errors:
                    user_result['errors'] = client_delete_errors
                    errors.extend([f'用户{user.username}：' + error for error in client_delete_errors])
                
                # 记录单个用户的操作日志
                log = OperationLog(
                    user_id=current_user.id,
                    operation_type='delete_user',
                    target_type='User',
                    target_id=str(user.id),
                    details=f'删除用户：{user.username}（批量删除第{i}个）'
                )
                db.session.add(log)
                db.session.commit()
                
            except Exception as e:
                db.session.rollback()  # 回滚当前用户的操作
                failed_count += 1
                error_msg = f'用户{user.username}删除失败：{str(e)}'
                errors.append(error_msg)
                user_result['errors'] = [str(e)]
                # 继续处理下一个用户
            
            results.append(user_result)
        
        # 记录批量操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='bulk_delete_users',
            target_type='User',
            target_id='bulk',
            details=f'批量删除用户：成功{success_count}个，失败{failed_count}个'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'批量删除完成：成功{success_count}个，失败{failed_count}个',
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors,
            'results': results,
            'total_processed': len(valid_users)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'批量删除用户失败：{str(e)}'
        }), 500


@admin.route('/bulk-delete-users-optimized', methods=['POST'])
@login_required
@admin_required
def bulk_delete_users_optimized():
    """批量删除用户（优化版本）
    
    使用批量操作优化的删除方式，提供更好的性能
    """
    try:
        # 验证AJAX请求
        if not request.is_json:
            return jsonify({'success': False, 'message': '请求格式错误'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求数据格式错误'}), 400
        
        user_ids = data.get('user_ids', [])
        
        # 验证必填字段
        if not user_ids:
            return jsonify({'success': False, 'message': '请选择要删除的用户'}), 400
        
        # 获取选中的用户
        users = User.query.filter(User.id.in_(user_ids)).all()
        if not users:
            return jsonify({'success': False, 'message': '未找到选中的用户'}), 400
        
        # 检查是否包含当前用户或管理员
        invalid_users = []
        valid_users = []
        for user in users:
            if user.id == current_user.id:
                invalid_users.append(f'用户{user.username}：不能删除当前登录的管理员账号')
            elif user.is_admin:
                invalid_users.append(f'用户{user.username}：不能删除其他管理员账号')
            else:
                valid_users.append(user)
        
        if invalid_users and not valid_users:
            return jsonify({
                'success': False, 
                'message': '包含无法删除的用户：\n' + '\n'.join(invalid_users)
            }), 400
        
        # 初始化统计
        success_count = 0
        failed_count = 0
        errors = []
        
        # 如果有无效用户，添加到错误列表
        if invalid_users:
            errors.extend(invalid_users)
            failed_count += len(invalid_users)
        
        if not valid_users:
            return jsonify({
                'success': False,
                'message': '没有可删除的有效用户',
                'errors': errors
            }), 400
        
        adguard = AdGuardService()
        
        # 收集所有需要删除的客户端名称
        all_client_names = []
        for user in valid_users:
            for mapping in user.client_mappings:
                all_client_names.append(mapping.client_name)
        
        # 批量删除AdGuard Home客户端
        client_delete_errors = []
        if all_client_names:
            try:
                # 使用批量删除API
                result = adguard.batch_delete_clients(all_client_names, skip_missing=True)
                if result.get('errors'):
                    client_delete_errors.extend(result['errors'])
            except Exception as e:
                client_delete_errors.append(f"批量删除AdGuard客户端失败：{str(e)}")
        
        # 从AdGuardHome的允许客户端列表中移除所有客户端ID
        try:
            access_list = adguard._make_request('GET', '/access/list')
            allowed_clients = access_list.get('allowed_clients', [])
            
            clients_to_remove = []
            for user in valid_users:
                for mapping in user.client_mappings:
                    for client_id in mapping.client_ids:
                        if client_id in allowed_clients:
                            allowed_clients.remove(client_id)
                            clients_to_remove.append(client_id)
            
            if clients_to_remove:
                access_data = {
                    'allowed_clients': allowed_clients,
                    'disallowed_clients': access_list.get('disallowed_clients', []),
                    'blocked_hosts': access_list.get('blocked_hosts', [])
                }
                adguard._make_request('POST', '/access/set', json=access_data)
        except Exception as e:
            client_delete_errors.append(f"从允许列表移除客户端ID失败：{str(e)}")
        
        # 批量删除数据库记录
        try:
            # 删除所有关联的客户端映射记录
            for user in valid_users:
                for mapping in user.client_mappings:
                    db.session.delete(mapping)
            
            # 删除所有关联的反馈记录
            from app.models.feedback import Feedback
            for user in valid_users:
                feedbacks = Feedback.query.filter_by(user_id=user.id).all()
                for feedback in feedbacks:
                    db.session.delete(feedback)
            
            # 删除用户记录
            for user in valid_users:
                db.session.delete(user)
            
            # 提交所有更改
            db.session.commit()
            success_count = len(valid_users)
            
            # 提交所有更改
            db.session.commit()
            success_count = len(valid_users)
            
            # 返回成功结果
            return jsonify({
                'success': True,
                'message': f'成功删除 {success_count} 个用户',
                'client_delete_errors': client_delete_errors if client_delete_errors else None
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'删除数据库记录失败：{str(e)}'
            }), 500
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'批量删除用户失败：{str(e)}'
        }), 500




@admin.route('/adguard-clients')
@login_required
@admin_required
def adguard_clients():
    """查询所有AdGuard Home客户端并匹配现有用户"""
    try:
        adguard_service = AdGuardService()
        
        # 获取所有客户端信息
        clients_data = adguard_service._make_request('GET', '/clients')
        
        # 获取所有用户的客户端映射
        all_user_mappings = ClientMapping.query.all()
        user_client_names = {mapping.client_name for mapping in all_user_mappings}
        user_client_ids = set()
        for mapping in all_user_mappings:
            user_client_ids.update(mapping.client_ids)
        
        # 获取允许的客户端ID列表
        try:
            access_list = adguard_service._make_request('GET', '/access/list')
            allowed_client_ids = set(access_list.get('allowed_clients', []))
        except Exception:
            allowed_client_ids = set()
        
        # 格式化客户端数据并进行匹配
        all_clients = []
        matched_clients = set()
        unmatched_clients = []
        
        # 处理手动配置的客户端
        if 'clients' in clients_data:
            for client in clients_data['clients']:
                client_name = client.get('name', '')
                client_ids = client.get('ids', [])
                
                # 检查是否匹配现有用户
                is_matched = client_name in user_client_names
                if is_matched:
                    matched_clients.add(client_name)
                
                client_info = {
                    'name': client_name,
                    'ids': client_ids,
                    'type': '手动配置',
                    'matched': is_matched,
                    'filtering_enabled': client.get('filtering_enabled', False),
                    'parental_enabled': client.get('parental_enabled', False),
                    'safebrowsing_enabled': client.get('safebrowsing_enabled', False),
                    'use_global_settings': client.get('use_global_settings', True),
                    'blocked_services': client.get('blocked_services', []),
                    'upstreams': client.get('upstreams', []),
                    'tags': client.get('tags', [])
                }
                all_clients.append(client_info)
                
                if not is_matched:
                    unmatched_clients.append({
                        'name': client_name,
                        'ids': client_ids,
                        'type': '手动配置'
                    })
        
        # 注释：只处理持久化客户端，不处理自动发现的客户端
        # 如需包含自动发现客户端，可取消注释以下代码块
        
        # 查找未匹配的允许客户端ID
        unmatched_allowed_ids = allowed_client_ids - user_client_ids
        
        return jsonify({
            'success': True,
            'clients': all_clients,
            'total_count': len(all_clients),
            'manual_count': len(clients_data.get('clients', [])),
            'matched_count': len(matched_clients),
            'unmatched_clients': unmatched_clients,
            'unmatched_allowed_ids': list(unmatched_allowed_ids),
            'has_unmatched': len(unmatched_clients) > 0 or len(unmatched_allowed_ids) > 0
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取AdGuard Home客户端失败: {str(e)}'
        }), 500


@admin.route('/delete-unmatched-clients', methods=['POST'])
@login_required
@admin_required
def delete_unmatched_clients():
    """删除未匹配的AdGuard客户端和允许ID"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'message': '请求格式错误'}), 400
        
        data = request.get_json()
        unmatched_clients = data.get('unmatched_clients', [])
        unmatched_allowed_ids = data.get('unmatched_allowed_ids', [])
        
        if not unmatched_clients and not unmatched_allowed_ids:
            return jsonify({'success': False, 'message': '没有需要删除的项目'}), 400
        
        # 获取AdGuard服务
        adguard_service = AdGuardService()
        
        deleted_clients = 0
        deleted_allowed_ids = 0
        errors = []
        
        # 删除未匹配的客户端
        for client in unmatched_clients:
            try:
                client_name = client.get('name')
                if client_name:
                    # 删除客户端
                    response = adguard_service._make_request('POST', '/clients/delete', {
                        'name': client_name
                    })
                    
                    if response is not None:  # 成功删除
                        deleted_clients += 1
                    else:
                        errors.append(f"删除客户端 {client_name} 失败")
                        
            except Exception as e:
                errors.append(f"删除客户端 {client.get('name', 'unknown')} 时出错: {str(e)}")
        
        # 删除未匹配的允许ID
        if unmatched_allowed_ids:
            try:
                # 获取当前访问设置
                access_data = adguard_service._make_request('GET', '/access/list')
                
                if access_data:
                    current_allowed_clients = access_data.get('allowed_clients', [])
                    
                    # 过滤掉未匹配的ID
                    new_allowed_clients = [client for client in current_allowed_clients 
                                         if client not in unmatched_allowed_ids]
                    
                    # 更新访问设置
                    update_data = {
                        'allowed_clients': new_allowed_clients,
                        'disallowed_clients': access_data.get('disallowed_clients', []),
                        'blocked_hosts': access_data.get('blocked_hosts', [])
                    }
                    
                    update_response = adguard_service._make_request('POST', '/access/set', update_data)
                    
                    if update_response is not None:
                        deleted_allowed_ids = len(unmatched_allowed_ids)
                    else:
                        errors.append("更新允许客户端列表失败")
                else:
                    errors.append("获取访问设置失败")
                    
            except Exception as e:
                errors.append(f"删除允许ID时出错: {str(e)}")
        
        # 记录操作日志
        try:
            log = OperationLog(
                user_id=current_user.id,
                operation_type='delete_unmatched_clients',
                target_type='AdGuard',
                target_id='unmatched',
                details=f'删除未匹配项：{deleted_clients}个客户端，{deleted_allowed_ids}个允许ID'
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            # 日志记录失败不影响主要操作
            pass
        
        return jsonify({
            'success': True,
            'deleted_clients': deleted_clients,
            'deleted_allowed_ids': deleted_allowed_ids,
            'errors': errors,
            'message': f'删除完成: {deleted_clients}个客户端, {deleted_allowed_ids}个允许ID'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'删除操作失败: {str(e)}'
        }), 500
        
        # 记录批量操作日志
        try:
            log = OperationLog(
                user_id=current_user.id,
                operation_type='bulk_delete_users_optimized',
                target_type='User',
                target_id='bulk',
                details=f'批量删除用户（优化版）：成功{success_count}个，失败{failed_count}个'
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            # 日志记录失败不影响主要操作
            pass
        
        # 合并所有错误信息
        if client_delete_errors:
            errors.extend(client_delete_errors)
        
        return jsonify({
            'success': True,
            'message': f'批量删除完成：成功{success_count}个，失败{failed_count}个',
            'success_count': success_count,
            'failed_count': failed_count,
            'errors': errors,
            'total_processed': len(valid_users)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'批量删除用户失败：{str(e)}'
        }), 500


@admin.route('/delete-user-progressive/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user_progressive(user_id):
    """逐个删除用户的API端点
    
    用于支持前端实时显示删除进度
    """
    try:
        # 获取用户
        user = User.query.get_or_404(user_id)
        
        # 检查是否为当前用户或管理员
        if user.id == current_user.id:
            return jsonify({
                'success': False, 
                'message': '不能删除当前登录的管理员账号',
                'username': user.username
            }), 200  # 改为200状态码，避免前端认为是服务器错误
        elif user.is_admin:
            return jsonify({
                'success': False, 
                'message': f'不能删除管理员账号：{user.username}',
                'username': user.username
            }), 200  # 改为200状态码，避免前端认为是服务器错误
        
        user_result = {
            'username': user.username,
            'success': False,
            'errors': []
        }
        
        client_delete_errors = []
        
        # 优化AdGuardHome操作，增加超时处理
        try:
            adguard = AdGuardService()
            
            # 删除用户的AdGuardHome客户端（增加超时处理）
            for mapping in user.client_mappings:
                try:
                    # 设置较短的超时时间，避免长时间等待
                    adguard.delete_client(mapping.client_name)
                except Exception as e:
                    # 记录错误但不阻止删除流程
                    client_delete_errors.append(f"客户端 {mapping.client_name} 删除失败：{str(e)}")
            
            # 从AdGuardHome的允许客户端列表中移除用户的客户端ID
            try:
                access_list = adguard._make_request('GET', '/access/list')
                allowed_clients = access_list.get('allowed_clients', [])
                
                clients_to_remove = []
                for mapping in user.client_mappings:
                    for client_id in mapping.client_ids:
                        if client_id in allowed_clients:
                            allowed_clients.remove(client_id)
                            clients_to_remove.append(client_id)
                
                if clients_to_remove:
                    access_data = {
                        'allowed_clients': allowed_clients,
                        'disallowed_clients': access_list.get('disallowed_clients', []),
                        'blocked_hosts': access_list.get('blocked_hosts', [])
                    }
                    adguard._make_request('POST', '/access/set', json=access_data)
            except Exception as e:
                client_delete_errors.append(f"从允许列表移除客户端ID失败：{str(e)}")
        except Exception as e:
            # AdGuardHome服务完全不可用时，记录错误但继续删除用户
            client_delete_errors.append(f"AdGuardHome服务不可用：{str(e)}")
        
        # 删除所有关联的客户端映射记录
        for mapping in user.client_mappings:
            db.session.delete(mapping)
        
        # 处理用户的反馈记录
        from app.models.feedback import Feedback
        feedbacks = Feedback.query.filter_by(user_id=user.id).all()
        for feedback in feedbacks:
            db.session.delete(feedback)
        
        # 删除用户记录
        db.session.delete(user)
        db.session.commit()
        
        user_result['success'] = True
        
        # 如果有客户端删除失败，记录警告
        if client_delete_errors:
            user_result['errors'] = client_delete_errors
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='delete_user',
            target_type='User',
            target_id=str(user.id),
            details=f'删除用户：{user.username}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify(user_result)
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False, 
            'message': f'删除用户失败：{str(e)}',
            'username': user.username if 'user' in locals() else 'Unknown',
            'errors': [str(e)]
        }), 200  # 改为200状态码，让前端正常处理错误

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


@admin.route('/api/clients/<int:mapping_id>', methods=['DELETE'])
@login_required
@admin_required
def admin_delete_client(mapping_id):
    """管理员删除客户端API"""
    try:
        # 获取客户端映射
        mapping = ClientMapping.query.get_or_404(mapping_id)
        
        # 检查是否为第一个客户端（不允许删除）
        user_mappings = ClientMapping.query.filter_by(user_id=mapping.user_id).order_by(ClientMapping.created_at).all()
        if user_mappings and user_mappings[0].id == mapping_id:
            return jsonify({
                'success': False,
                'message': '不能删除主客户端'
            }), 400
        
        client_name = mapping.client_name
        client_ids = mapping.client_ids
        user = mapping.user
        
        # 初始化AdGuard服务
        adguard = AdGuardService()
        
        try:
            # 从AdGuard Home删除客户端
            adguard.delete_client(client_name)
            print(f"已从AdGuard Home删除客户端: {client_name}")
        except Exception as e:
            print(f"从AdGuard Home删除客户端失败: {str(e)}")
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
                print(f"已从允许列表中移除客户端ID: {clients_to_remove}")
        except Exception as e:
            print(f"从允许列表移除客户端ID失败: {str(e)}")
            # 继续执行，不影响数据库删除
        
        # 删除数据库记录
        db.session.delete(mapping)
        
        # 记录操作日志
        operation_log = OperationLog(
            user_id=current_user.id,
            operation_type='DELETE',
            target_type='CLIENT',
            target_id=client_name,
            details=f'管理员删除用户 {user.username} 的客户端: {client_name}'
        )
        db.session.add(operation_log)
        db.session.commit()
        
        print(f"管理员 {current_user.username} 成功删除用户 {user.username} 的客户端: {client_name}")
        
        return jsonify({
            'success': True,
            'message': '客户端删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"管理员删除客户端API错误: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500


@admin.route('/operation-logs')
@login_required
@admin_required
def operation_logs():
    """操作日志页面"""
    page = request.args.get('page', 1, type=int)
    pagination = OperationLog.query.order_by(OperationLog.created_at.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False
    )
    logs = pagination.items
    return render_template('admin/operation_logs.html', logs=logs, pagination=pagination)

@admin.route('/email-config', methods=['GET', 'POST'])
@login_required
@admin_required
def email_config():
    """邮箱配置管理"""
    config = EmailConfig.query.first()
    if not config:
        config = EmailConfig()

    if request.method == 'POST':
        config.mail_server = request.form.get('mail_server')
        config.mail_port = request.form.get('mail_port', type=int)
        config.mail_username = request.form.get('mail_username')
        
        # 只有在提供了新密码时才更新
        new_password = request.form.get('mail_password')
        if new_password:
            config.mail_password = new_password
            
        config.mail_use_tls = 'mail_use_tls' in request.form
        config.mail_default_sender = request.form.get('mail_default_sender')
        config.verification_code_expire_minutes = request.form.get('verification_code_expire_minutes', 10, type=int)

        db.session.add(config)
        db.session.commit()
        flash('邮箱配置已更新。', 'success')
        return redirect(url_for('admin.email_config'))
    
    if not config.id:
        config.mail_server = 'smtp.example.com'
        config.mail_port = 587
        config.mail_use_tls = True
        config.verification_code_expire_minutes = 10

    return render_template('admin/email_config.html', config=config)

@admin.route('/test-email-config', methods=['POST'])
@login_required
@admin_required
def test_email_config():
    """测试邮件配置"""
    data = request.get_json()
    try:
        # 创建一个临时的EmailConfig对象用于测试，不保存到数据库
        temp_config = EmailConfig(
            mail_server=data.get('mail_server'),
            mail_port=int(data.get('mail_port')),
            mail_username=data.get('mail_username'),
            mail_password=data.get('mail_password'),
            mail_use_tls=data.get('mail_use_tls'),
            mail_default_sender=data.get('mail_default_sender')
        )

        is_valid, error_msg = temp_config.validate()
        if not is_valid:
            return jsonify({'success': False, 'error': f'配置无效: {error_msg}'})

        # 使用临时配置发送测试邮件
        success = EmailService.send_email(
            to=data.get('mail_username'), # 发送测试邮件到配置中的用户名邮箱
            subject="邮箱配置测试",
            template='test_email',
            config_override=temp_config,
            test_message="这是一封来自AdGuardHome Manager的测试邮件。如果您能收到此邮件，说明您的邮箱配置正确。"
        )
        
        if success:
            return jsonify({'success': True, 'message': '测试邮件已发送，请检查收件箱。'})
        else:
            return jsonify({'success': False, 'error': '邮件发送失败，请检查服务器日志获取详细信息。'})
    except Exception as e:
        current_app.logger.error(f'测试邮件发送异常: {str(e)}')
        return jsonify({'success': False, 'error': f'发送测试邮件时发生错误: {str(e)}'})

@admin.route('/feedbacks')
@login_required
@admin_required
def feedbacks():
    page = request.args.get('page', 1, type=int)
    pagination = Feedback.query.order_by(Feedback.created_at.desc()).paginate(
        page=page, per_page=current_app.config['ITEMS_PER_PAGE'], error_out=False
    )
    feedbacks = pagination.items
    return render_template('admin/feedbacks.html', feedbacks=feedbacks, pagination=pagination)

@admin.route('/api/feedbacks')
@login_required
@admin_required
def api_feedbacks():
    """提供反馈数据的API接口"""
    feedback_id = request.args.get('id', type=int)
    if feedback_id:
        feedback = Feedback.query.get_or_404(feedback_id)
        return jsonify({'items': [feedback.to_dict()]})

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', 'all')

    query = Feedback.query
    if status != 'all':
        query = query.filter_by(status=status)

    pagination = query.order_by(Feedback.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    feedbacks = pagination.items
    return jsonify({
        'items': [feedback.to_dict() for feedback in feedbacks],
        'total': pagination.total,
        'pages': pagination.pages,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev,
        'page': pagination.page
    })

@admin.route('/api/feedback/<int:feedback_id>/reply', methods=['POST'])
@login_required
@admin_required
def reply_feedback(feedback_id):
    """回复用户反馈"""
    feedback = Feedback.query.get_or_404(feedback_id)
    data = request.get_json()
    reply = data.get('reply')
    if not reply:
        return jsonify({'success': False, 'error': '回复内容不能为空'}), 400

    feedback.admin_reply = reply
    feedback.updated_at = beijing_time()
    db.session.commit()
    return jsonify({'success': True, 'message': '回复成功'})

@admin.route('/api/feedback/<int:feedback_id>/close', methods=['POST'])
@login_required
@admin_required
def close_feedback(feedback_id):
    """关闭用户反馈"""
    feedback = Feedback.query.get_or_404(feedback_id)
    feedback.close_feedback(current_user.id)
    db.session.commit()
    return jsonify({'success': True, 'message': '留言已关闭'})





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

@admin.route('/api/query-log/advanced-search', methods=['POST'])
@login_required
@admin_required
def query_log_advanced_search():
    """高级搜索查询日志 API

    支持复杂的过滤条件、分页和统计
    """
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        page_size = data.get('page_size', 50)
        older_than = data.get('older_than')

        adguard_service = AdGuardService()
        
        # 调用新的服务层方法
        result = adguard_service.get_query_log_advanced(
            filters=filters,
            limit=page_size,
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

@admin.route('/users/edit-vip', methods=['POST'])
@login_required
@admin_required
def edit_user_vip():
    """编辑用户VIP时间
    
    接收用户ID和新的VIP到期时间，更新用户的VIP状态。
    如果vip_expire_time为空，则取消用户的VIP状态。
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        vip_expire_time = data.get('vip_expire_time')
        
        if not user_id:
            return jsonify({
                'success': False,
                'message': '用户ID不能为空'
            }), 400
            
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '用户不存在'
            }), 404
            
        # 记录操作日志
        old_vip_status = f"VIP到期时间: {user.vip_expire_time}" if user.vip_expire_time else "非VIP用户"
        
        if vip_expire_time:
            # 设置VIP时间
            from datetime import datetime
            try:
                expire_time = datetime.fromisoformat(vip_expire_time.replace('T', ' '))
                user.vip_expire_time = expire_time
                user.is_vip_user = True
                new_vip_status = f"VIP到期时间: {expire_time}"
            except ValueError:
                return jsonify({
                    'success': False,
                    'message': '时间格式错误'
                }), 400
        else:
            # 取消VIP
            user.vip_expire_time = None
            user.is_vip_user = False
            new_vip_status = "取消VIP状态"
            
        db.session.commit()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='UPDATE',
            target_type='USER',
            target_id=str(user.id),
            details=f"修改用户 {user.username} 的VIP状态: {old_vip_status} -> {new_vip_status}"
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'VIP状态更新成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'更新失败: {str(e)}'
        }), 500


@admin.route('/users/bulk-vip', methods=['POST'])
@login_required
@admin_required
def bulk_vip_upgrade():
    """批量VIP升级功能
    
    支持批量为多个用户设置VIP状态，可以选择延长现有VIP时间或重置VIP时间。
    支持预览模式，可以在实际执行前查看操作结果。
    """
    try:
        data = request.get_json()
        user_ids = data.get('user_ids', [])
        vip_days = data.get('vip_days')
        extend_existing = data.get('extend_existing', True)
        preview_only = data.get('preview_only', False)
        
        if not user_ids:
            return jsonify({
                'success': False,
                'message': '用户ID列表不能为空'
            }), 400
            
        if vip_days is None:
            return jsonify({
                'success': False,
                'message': 'VIP天数不能为空'
            }), 400
            
        # 验证用户ID并获取用户信息
        valid_users = []
        invalid_users = []
        
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user:
                valid_users.append(user)
            else:
                invalid_users.append(user_id)
        
        if not valid_users:
            return jsonify({
                'success': False,
                'message': '没有找到有效的用户'
            }), 400
            
        # 计算新的VIP到期时间
        from datetime import datetime, timedelta
        now = datetime.now()
        
        preview_data = {
            'valid_users': [],
            'invalid_users': invalid_users,
            'summary': ''
        }
        
        success_count = 0
        failed_count = 0
        
        for user in valid_users:
            try:
                # 计算新的到期时间
                if vip_days == -1:
                    # 永久VIP
                    new_expire_time = datetime(2099, 12, 31, 23, 59, 59)
                    new_expire_str = '永久VIP'
                elif vip_days == 0:
                    # 取消VIP
                    new_expire_time = None
                    new_expire_str = '取消VIP'
                else:
                    # 设置指定天数的VIP
                    if extend_existing and user.vip_expire_time and user.vip_expire_time > now:
                        # 在现有VIP基础上延长
                        base_time = user.vip_expire_time
                    else:
                        # 从现在开始计算
                        base_time = now
                    
                    new_expire_time = base_time + timedelta(days=vip_days)
                    new_expire_str = new_expire_time.strftime('%Y-%m-%d %H:%M:%S')
                
                # 添加到预览数据
                user_preview = {
                    'id': user.id,
                    'username': user.username,
                    'current_vip_expire': user.vip_expire_time.strftime('%Y-%m-%d %H:%M:%S') if user.vip_expire_time else None,
                    'new_expire_time': new_expire_str
                }
                preview_data['valid_users'].append(user_preview)
                
                # 如果不是预览模式，执行实际更新
                if not preview_only:
                    old_vip_status = f"VIP到期时间: {user.vip_expire_time}" if user.vip_expire_time else "非VIP用户"
                    
                    if new_expire_time:
                        user.vip_expire_time = new_expire_time
                        user.is_vip_user = True
                    else:
                        user.vip_expire_time = None
                        user.is_vip_user = False
                    
                    # 记录操作日志
                    log = OperationLog(
                        user_id=current_user.id,
                        operation_type='BULK_UPDATE',
                        target_type='USER',
                        target_id=str(user.id),
                        details=f"批量修改用户 {user.username} 的VIP状态: {old_vip_status} -> {new_expire_str}"
                    )
                    db.session.add(log)
                    success_count += 1
                    
            except Exception as e:
                current_app.logger.error(f"处理用户 {user.id} 时出错: {str(e)}")
                failed_count += 1
                continue
        
        # 生成操作摘要
        if vip_days == -1:
            operation_desc = "设为永久VIP"
        elif vip_days == 0:
            operation_desc = "取消VIP状态"
        else:
            if extend_existing:
                operation_desc = f"延长VIP {vip_days} 天（在现有基础上）"
            else:
                operation_desc = f"设置VIP {vip_days} 天（从现在开始）"
        
        preview_data['summary'] = f"将为 {len(valid_users)} 个用户{operation_desc}"
        
        if preview_only:
            return jsonify({
                'success': True,
                'preview': preview_data
            })
        else:
            # 提交数据库更改
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'批量VIP升级完成',
                'success_count': success_count,
                'failed_count': failed_count,
                'total_count': len(valid_users)
            })
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"批量VIP升级失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'批量升级失败: {str(e)}'
        }), 500


@admin.route('/vip-filter-rules')
@login_required
@admin_required
def vip_filter_rules():
    """VIP专属过滤规则管理页面"""
    return render_template('admin/vip_filter_rules.html')


@admin.route('/api/vip-filter-rules', methods=['GET'])
@login_required
@admin_required
def get_vip_filter_rules():
    """获取VIP专属过滤规则"""
    try:
        adguard_service = AdGuardService()
        
        # 获取过滤器状态，包含用户规则
        response = adguard_service._make_request('GET', '/filtering/status')
        
        if not response:
            return jsonify({
                'success': False,
                'error': 'AdGuard Home服务不可用'
            }), 500
        
        # 解析规则，筛选出VIP专属规则（包含user_child标签的规则）
        all_rules = response.get('user_rules', [])
        vip_rules = []
        
        for rule in all_rules:
            # 检查规则是否包含user_child标签
            if '$ctag=user_child' in rule:
                # 解析规则信息
                rule_parts = rule.split(' ! ')
                actual_rule = rule_parts[0].replace('$ctag=user_child', '').strip()
                description = rule_parts[1] if len(rule_parts) > 1 else ''
                
                # 处理禁用的规则（以!开头）
                enabled = True
                if actual_rule.startswith('!'):
                    enabled = False
                    actual_rule = actual_rule[1:].strip()
                
                vip_rules.append({
                    'rule': actual_rule,
                    'description': description,
                    'enabled': enabled
                })
        
        return jsonify({
            'success': True,
            'rules': vip_rules
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/vip-filter-rules', methods=['POST'])
@login_required
@admin_required
def add_vip_filter_rule():
    """添加VIP专属过滤规则"""
    try:
        data = request.get_json()
        rule = data.get('rule', '').strip()
        description = data.get('description', '').strip()
        enabled = data.get('enabled', True)
        
        if not rule:
            return jsonify({
                'success': False,
                'error': '规则不能为空'
            }), 400
        
        adguard_service = AdGuardService()
        
        # 获取过滤器状态，包含用户规则
        response = adguard_service._make_request('GET', '/filtering/status')
        
        if not response:
            return jsonify({
                'success': False,
                'error': 'AdGuard Home服务不可用'
            }), 500
        
        current_rules = response.get('user_rules', [])
        
        # 构建新的VIP专属规则
        vip_rule = f"{rule}$ctag=user_child"
        if description:
            vip_rule += f" ! {description}"
        
        # 如果规则被禁用，在前面添加!
        if not enabled:
            vip_rule = f"!{vip_rule}"
        
        # 检查规则是否已存在
        rule_exists = False
        for existing_rule in current_rules:
            if rule in existing_rule and '$ctag=user_child' in existing_rule:
                rule_exists = True
                break
        
        if rule_exists:
            return jsonify({
                'success': False,
                'error': '该规则已存在'
            }), 400
        
        # 添加新规则
        new_rules = current_rules + [vip_rule]
        
        # 更新规则
        update_response = adguard_service._make_request('POST', '/filtering/set_rules', json={
            'rules': new_rules
        })
        
        if update_response is None:
            return jsonify({
                'success': False,
                'error': '更新规则失败'
            }), 500
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='add_vip_filter_rule',
            target_type='FilterRule',
            target_id=rule,
            details=f'添加VIP专属过滤规则：{rule}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '规则添加成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/vip-filter-rules/<int:rule_index>', methods=['PUT'])
@login_required
@admin_required
def update_vip_filter_rule(rule_index):
    """更新VIP专属过滤规则"""
    try:
        data = request.get_json()
        rule = data.get('rule', '').strip()
        description = data.get('description', '').strip()
        enabled = data.get('enabled', True)
        
        if not rule:
            return jsonify({
                'success': False,
                'error': '规则不能为空'
            }), 400
        
        adguard_service = AdGuardService()
        
        # 获取过滤器状态，包含用户规则
        response = adguard_service._make_request('GET', '/filtering/status')
        
        if not response:
            return jsonify({
                'success': False,
                'error': 'AdGuard Home服务不可用'
            }), 500
        
        current_rules = response.get('user_rules', [])
        
        # 找到VIP专属规则
        vip_rules = []
        vip_rule_indices = []
        
        for i, existing_rule in enumerate(current_rules):
            if '$ctag=user_child' in existing_rule:
                vip_rules.append(existing_rule)
                vip_rule_indices.append(i)
        
        if rule_index >= len(vip_rules):
            return jsonify({
                'success': False,
                'error': '规则索引无效'
            }), 400
        
        # 构建新的VIP专属规则
        vip_rule = f"{rule}$ctag=user_child"
        if description:
            vip_rule += f" ! {description}"
        
        # 如果规则被禁用，在前面添加!
        if not enabled:
            vip_rule = f"!{vip_rule}"
        
        # 更新规则列表
        actual_index = vip_rule_indices[rule_index]
        current_rules[actual_index] = vip_rule
        
        # 更新规则
        update_response = adguard_service._make_request('POST', '/filtering/set_rules', json={
            'rules': current_rules
        })
        
        if update_response is None:
            return jsonify({
                'success': False,
                'error': '更新规则失败'
            }), 500
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='update_vip_filter_rule',
            target_type='FilterRule',
            target_id=rule,
            details=f'更新VIP专属过滤规则：{rule}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '规则更新成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/api/vip-filter-rules/<int:rule_index>', methods=['DELETE'])
@login_required
@admin_required
def delete_vip_filter_rule(rule_index):
    """删除VIP专属过滤规则"""
    try:
        adguard_service = AdGuardService()
        
        # 获取过滤器状态，包含用户规则
        response = adguard_service._make_request('GET', '/filtering/status')
        
        if not response:
            return jsonify({
                'success': False,
                'error': 'AdGuard Home服务不可用'
            }), 500
        
        current_rules = response.get('user_rules', [])
        
        # 找到VIP专属规则
        vip_rules = []
        vip_rule_indices = []
        
        for i, existing_rule in enumerate(current_rules):
            if '$ctag=user_child' in existing_rule:
                vip_rules.append(existing_rule)
                vip_rule_indices.append(i)
        
        if rule_index >= len(vip_rules):
            return jsonify({
                'success': False,
                'error': '规则索引无效'
            }), 400
        
        # 获取要删除的规则信息（用于日志）
        rule_to_delete = vip_rules[rule_index]
        
        # 删除规则
        actual_index = vip_rule_indices[rule_index]
        current_rules.pop(actual_index)
        
        # 更新规则
        update_response = adguard_service._make_request('POST', '/filtering/set_rules', json={
            'rules': current_rules
        })
        
        if update_response is None:
            return jsonify({
                'success': False,
                'error': '删除规则失败'
            }), 500
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='delete_vip_filter_rule',
            target_type='FilterRule',
            target_id=str(rule_index),
            details=f'删除VIP专属过滤规则：{rule_to_delete}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '规则删除成功'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin.route('/vip-config', methods=['GET', 'POST'])
@login_required
@admin_required
def vip_config():
    """VIP配置管理页面
    
    允许管理员配置VIP相关设置，如VIP价格、时长、升级条件等。
    """
    config = VipConfig.get_config()
    
    if request.method == 'POST':
        try:
            # 获取表单数据
            vip_price = float(request.form.get('vip_price', 30.0))
            vip_duration_days = int(request.form.get('vip_duration_days', 365))
            auto_upgrade = 'auto_upgrade' in request.form
            min_vip_amount = float(request.form.get('min_vip_amount', 30.0))
            cumulative_upgrade = 'cumulative_upgrade' in request.form
            vip_title = request.form.get('vip_title', '').strip()
            vip_description = request.form.get('vip_description', '').strip()
            enabled = 'enabled' in request.form
            
            # 更新配置
            config.vip_price = vip_price
            config.vip_duration_days = vip_duration_days
            config.auto_upgrade = auto_upgrade
            config.min_vip_amount = min_vip_amount
            config.cumulative_upgrade = cumulative_upgrade
            config.vip_title = vip_title or 'VIP会员'
            config.vip_description = vip_description
            config.enabled = enabled
            
            db.session.commit()
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_vip_config',
                target_type='SYSTEM',
                target_id='vip_config',
                details=f'更新VIP配置：价格={vip_price}，时长={vip_duration_days}天，最小金额={min_vip_amount}，启用={enabled}'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('VIP配置已更新', 'success')
            return redirect(url_for('admin.vip_config'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'error')
    
    return render_template('admin/vip_config.html', config=config)

@admin.route('/send-bulk-email', methods=['POST'])
@login_required
@admin_required
def send_bulk_email():
    """批量发送邮件给选中的用户"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求数据格式错误'}), 400
        
        user_ids = data.get('user_ids', [])
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()
        additional_info = data.get('additional_info', '').strip()
        
        # 验证必填字段
        if not user_ids:
            return jsonify({'success': False, 'message': '请选择要发送邮件的用户'}), 400
        
        if not subject:
            return jsonify({'success': False, 'message': '请输入邮件主题'}), 400
            
        if not message:
            return jsonify({'success': False, 'message': '请输入邮件内容'}), 400
        
        # 获取选中的用户
        users = User.query.filter(User.id.in_(user_ids)).all()
        if not users:
            return jsonify({'success': False, 'message': '未找到选中的用户'}), 400
        
        # 过滤出有邮箱的用户
        users_with_email = [user for user in users if user.email]
        if not users_with_email:
            return jsonify({'success': False, 'message': '选中的用户中没有设置邮箱的用户'}), 400
        
        # 记录操作日志
        operation_log = OperationLog(
            user_id=current_user.id,
            operation_type='bulk_email',
             target_type='User',
             target_id='bulk_email',
             details=f'批量发送邮件给 {len(users_with_email)} 个用户，主题：{subject}',
            
            created_at=beijing_time()
        )
        db.session.add(operation_log)
        db.session.commit()
        
        # 发送邮件统计
        success_count = 0
        failed_count = 0
        failed_emails = []
        
        # 逐个发送邮件
        for user in users_with_email:
            try:
                success = EmailService.send_email(
                    to=user.email,
                    subject=subject,
                    template='bulk_email',
                    message=message,
                    additional_info=additional_info,
                    username=user.username
                )
                
                if success:
                    success_count += 1
                    current_app.logger.info(f'批量邮件发送成功：{user.email}')
                else:
                    failed_count += 1
                    failed_emails.append(user.email)
                    current_app.logger.error(f'批量邮件发送失败：{user.email}')
                    
            except Exception as e:
                failed_count += 1
                failed_emails.append(user.email)
                current_app.logger.error(f'批量邮件发送异常：{user.email}, 错误：{str(e)}')
        
        # 返回发送结果
        result = {
            'success': True,
            'message': f'邮件发送完成',
            'success_count': success_count,
            'failed_count': failed_count,
            'total_count': len(users_with_email)
        }
        
        if failed_emails:
            result['failed_emails'] = failed_emails
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f'批量邮件发送异常：{str(e)}')
        return jsonify({
            'success': False,
            'message': f'邮件发送失败：{str(e)}'
        }), 500


@admin.route('/api/user/by-client/<client_id>', methods=['GET'])
@login_required
@admin_required
def get_user_by_client_id(client_id):
    """根据客户端ID获取用户信息API"""
    try:
        from app.models.user import User
        from app.models.client_mapping import ClientMapping
        import json
        
        # 查找包含该客户端ID的客户端映射
        client_mappings = ClientMapping.query.all()
        target_mapping = None
        
        for mapping in client_mappings:
            client_ids = json.loads(mapping._client_ids)
            if client_id in client_ids:
                target_mapping = mapping
                break
        
        if not target_mapping:
            return jsonify({
                'success': False,
                'message': '客户端ID不存在'
            }), 404
        
        # 获取对应的用户信息
        user = User.query.get(target_mapping.user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '用户不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'client_name': target_mapping.client_name
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取用户信息失败: {str(e)}'
        }), 500


@admin.route('/api/donation-records/add', methods=['POST'])
@login_required
@admin_required
def add_donation_record():
    """手动添加捐赠记录
    
    管理员可以使用此接口为用户手动添加捐赠记录，用于处理线下捐赠等情况。
    """
    try:
        data = request.get_json()
        
        # 验证必需字段
        required_fields = ['user_id', 'donor_name', 'amount', 'payment_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'缺少必需字段：{field}'
                }), 400
        
        user_id = int(data['user_id'])
        donor_name = data['donor_name'].strip()
        amount = float(data['amount'])
        payment_type = data['payment_type'].strip()
        trade_no = data.get('trade_no', '').strip()
        
        # 验证用户是否存在
        from app.models.user import User
        user = User.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 400
        
        # 验证金额
        if amount <= 0:
            return jsonify({
                'success': False,
                'error': '捐赠金额必须大于0'
            }), 400
        
        # 生成订单号
        import uuid
        import time
        order_id = f'MANUAL_{int(time.time())}_{str(uuid.uuid4())[:8].upper()}'
        
        # 创建捐赠记录
        from app.models.donation_record import DonationRecord
        from app.utils.timezone import beijing_time
        donation_record = DonationRecord(
            order_id=order_id,
            donor_name=donor_name,
            amount=amount,
            payment_type=payment_type,
            trade_no=trade_no if trade_no else None,
            status='success',  # 手动添加的记录直接设为成功状态
            user_id=user_id,
            paid_at=beijing_time()  # 设置支付时间为当前时间
        )
        db.session.add(donation_record)
        db.session.flush()  # 获取记录ID
        
        # 处理VIP升级逻辑
        donation_record.process_vip_upgrade()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='add_donation_record',
            target_type='donation_record',
            target_id=str(donation_record.id),
            details=f'手动添加捐赠记录：用户={user.username}，捐赠者={donor_name}，金额={amount}，支付方式={payment_type}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '捐赠记录添加成功',
            'record': donation_record.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'数据格式错误：{str(e)}'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'添加捐赠记录失败：{str(e)}'
        }), 500


@admin.route('/api/donation-records/clear', methods=['POST'])
@login_required
@admin_required
def clear_donation_records():
    """清空所有捐赠记录
    
    管理员可以使用此接口清空所有捐赠记录，用于重置捐赠排行榜。
    此操作不可逆，请谨慎使用。
    """
    try:
        # 获取要删除的记录数量
        record_count = DonationRecord.query.count()
        
        if record_count == 0:
            return jsonify({
                'success': True,
                'message': '没有捐赠记录需要清空',
                'deleted_count': 0
            })
        
        # 删除所有捐赠记录
        DonationRecord.query.delete()
        db.session.commit()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='clear_donation_records',
            target_type='donation_record',
            target_id='all',
            details=f'清空所有捐赠记录，共删除 {record_count} 条记录'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功清空所有捐赠记录，共删除 {record_count} 条记录',
            'deleted_count': record_count
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'清空捐赠记录失败：{str(e)}'
        }), 500


@admin.route('/donation-records')
@login_required
@admin_required
def donation_records():
    """捐赠记录管理页面
    
    显示所有捐赠记录，并提供清空功能
    """
    # 获取所有捐赠记录，按创建时间倒序
    records = DonationRecord.query.order_by(DonationRecord.created_at.desc()).all()
    
    # 获取统计信息
    total_amount = DonationRecord.get_total_amount()
    total_count = DonationRecord.get_total_count()
    success_count = DonationRecord.query.filter_by(status='success').count()
    
    return render_template('admin/donation_records.html', 
                         records=records,
                         total_amount=total_amount,
                         total_count=total_count,
                         success_count=success_count)









@admin.route('/api/dns-rewrite/list', methods=['GET'])
@login_required
@admin_required
def dns_rewrite_list():
    """获取DNS重写规则列表"""
    try:
        svc = AdGuardService()
        rules = svc.get_rewrite_list()
        return jsonify({'success': True, 'rules': rules or []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-rewrite/add', methods=['POST'])
@login_required
@admin_required
def dns_rewrite_add():
    """添加单条DNS重写规则"""
    try:
        data = request.get_json() or {}
        domain = (data.get('domain') or '').strip()
        answer = (data.get('answer') or '').strip()
        if not domain or not answer:
            return jsonify({'success': False, 'error': '参数不完整'}), 400
        svc = AdGuardService()
        result = svc.add_rewrite_rule(domain, answer)
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_rewrite_add',
            target_type='dns_rewrite',
            target_id=domain,
            details=f'添加DNS重写：{domain} -> {answer}'
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-rewrite/delete', methods=['POST'])
@login_required
@admin_required
def dns_rewrite_delete():
    """删除单条DNS重写规则"""
    try:
        data = request.get_json() or {}
        domain = (data.get('domain') or '').strip()
        answer = (data.get('answer') or '').strip()
        if not domain or not answer:
            return jsonify({'success': False, 'error': '参数不完整'}), 400
        svc = AdGuardService()
        result = svc.delete_rewrite_rule(domain, answer)
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_rewrite_delete',
            target_type='dns_rewrite',
            target_id=domain,
            details=f'删除DNS重写：{domain} -> {answer}'
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-rewrite/import', methods=['POST'])
@login_required
@admin_required
def dns_rewrite_import():
    """通过外部链接导入DNS重写规则"""
    try:
        data = request.get_json() or {}
        url = (data.get('url') or '').strip()
        if not url:
            return jsonify({'success': False, 'error': 'URL不能为空'}), 400
        svc = AdGuardService()
        result = svc.import_rewrite_rules_from_url(url)
        # 记录日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_rewrite_import',
            target_type='dns_rewrite',
            target_id='import',
            details=f'从URL导入DNS重写：{url}，解析{result.get("rules_parsed",0)}条'
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': result.get('success', False), 'result': result}), (200 if result.get('success') else 400)
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-rewrite/update', methods=['PUT', 'POST'])
@login_required
@admin_required
def dns_rewrite_update():
    """更新DNS重写规则"""
    try:
        data = request.get_json() or {}
        target = data.get('target') or {}
        update = data.get('update') or {}
        target_domain = (target.get('domain') or '').strip()
        target_answer = (target.get('answer') or '').strip()
        new_domain = (update.get('domain') or '').strip()
        new_answer = (update.get('answer') or '').strip()
        if not target_domain or not target_answer or not new_domain or not new_answer:
            return jsonify({'success': False, 'error': '参数不完整'}), 400
        svc = AdGuardService()
        result = svc.update_rewrite_rule(target_domain, target_answer, new_domain, new_answer)
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_rewrite_update',
            target_type='dns_rewrite',
            target_id=target_domain,
            details=f'更新DNS重写：{target_domain} -> {target_answer} 到 {new_domain} -> {new_answer}'
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-rewrite/batch-add', methods=['POST'])
@login_required
@admin_required
def dns_rewrite_batch_add():
    """批量添加DNS重写规则，支持传入rules数组或纯文本text"""
    try:
        data = request.get_json() or {}
        rules = data.get('rules')
        text = data.get('text')
        svc = AdGuardService()
        if not rules and text:
            # 允许直接传入文本，后端解析
            rules = svc._parse_rewrite_rules_from_text(text)
        if not rules or not isinstance(rules, list):
            return jsonify({'success': False, 'error': '未提供有效规则'}), 400
        result = svc.batch_add_rewrite_rules(rules)
        # 记录日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_rewrite_batch_add',
            target_type='dns_rewrite',
            target_id='batch',
            details=f'批量添加DNS重写：成功{result.get("success",0)}条，失败{result.get("failed",0)}条'
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-rewrite/batch-delete', methods=['POST'])
@login_required
@admin_required
def dns_rewrite_batch_delete():
    """批量删除DNS重写规则"""
    try:
        data = request.get_json() or {}
        rules = data.get('rules')
        if not rules or not isinstance(rules, list):
            return jsonify({'success': False, 'error': '未提供有效规则'}), 400
        svc = AdGuardService()
        result = svc.batch_delete_rewrite_rules(rules)
        # 记录日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_rewrite_batch_delete',
            target_type='dns_rewrite',
            target_id='batch',
            details=f'批量删除DNS重写：成功{result.get("success",0)}条，失败{result.get("failed",0)}条'
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

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


@admin.route('/dns-config')
@login_required
@admin_required
def dns_config():
    """DNS配置管理页面"""
    config = DnsConfig.get_config()
    return render_template('admin/dns_config.html', config=config)

@admin.route('/system-config', methods=['GET', 'POST'])
@login_required
@admin_required
def system_config():
    """系统设置管理页面
    
    允许管理员配置系统全局设置，如是否允许新用户注册等。
    """
    config = SystemConfig.get_config()
    
    if request.method == 'POST':
        # 获取表单数据
        allow_registration = 'allow_registration' in request.form
        
        # 更新配置
        config.allow_registration = allow_registration
        db.session.commit()
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='update_system_config',
            target_type='SYSTEM',
            target_id='system_config',
            details=f'更新系统设置：允许注册={allow_registration}'
        )
        db.session.add(log)
        db.session.commit()
        
        flash('系统设置已更新', 'success')
        return redirect(url_for('admin.system_config'))
    
    return render_template('admin/system_config.html', config=config)


@admin.route('/api/dns-config', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_dns_config():
    """管理DNS配置API"""
    if request.method == 'GET':
        try:
            config = DnsConfig.get_config()
            return jsonify({
                'success': True,
                'config': config.to_dict()
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            config = DnsConfig.get_config()
            
            # 更新DNS-over-QUIC配置
            if 'doq_enabled' in data:
                config.doq_enabled = bool(data['doq_enabled'])
            if 'doq_server' in data:
                config.doq_server = data['doq_server'].strip()
            if 'doq_port' in data:
                config.doq_port = int(data['doq_port'])
            if 'doq_description' in data:
                config.doq_description = data['doq_description'].strip()
            
            # 更新DNS-over-TLS配置
            if 'dot_enabled' in data:
                config.dot_enabled = bool(data['dot_enabled'])
            if 'dot_server' in data:
                config.dot_server = data['dot_server'].strip()
            if 'dot_port' in data:
                config.dot_port = int(data['dot_port'])
            if 'dot_description' in data:
                config.dot_description = data['dot_description'].strip()
            
            # 更新DNS-over-HTTPS配置
            if 'doh_enabled' in data:
                config.doh_enabled = bool(data['doh_enabled'])
            if 'doh_server' in data:
                config.doh_server = data['doh_server'].strip()
            if 'doh_port' in data:
                config.doh_port = int(data['doh_port'])
            if 'doh_path' in data:
                config.doh_path = data['doh_path'].strip()
            if 'doh_description' in data:
                config.doh_description = data['doh_description'].strip()
            
            # 更新显示配置
            if 'display_title' in data:
                config.display_title = data['display_title'].strip()
            if 'display_description' in data:
                config.display_description = data['display_description'].strip()
            
            # 更新苹果配置文件控制
            if 'apple_config_enabled' in data:
                config.apple_config_enabled = bool(data['apple_config_enabled'])
            if 'apple_doh_config_enabled' in data:
                config.apple_doh_config_enabled = bool(data['apple_doh_config_enabled'])
            if 'apple_dot_config_enabled' in data:
                config.apple_dot_config_enabled = bool(data['apple_dot_config_enabled'])
            
            # 验证配置
            is_valid, error_msg = config.validate()
            if not is_valid:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 400
            
            db.session.commit()
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_dns_config',
                target_type='config',
                target_id='dns',
                details='更新DNS配置信息'
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'DNS配置已更新',
                'config': config.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@admin.route('/announcements')
@login_required
@admin_required
def announcements():
    """公告管理页面"""
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/announcements.html', announcements=announcements)

@admin.route('/announcements/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_announcement():
    """创建公告"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            announcement = Announcement(
                title=data.get('title'),
                content=data.get('content'),
                is_active=data.get('is_active', True),
                show_on_homepage=data.get('show_on_homepage', True),
                created_by=current_user.id
            )
            
            db.session.add(announcement)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '公告创建成功',
                'announcement': announcement.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return render_template('admin/create_announcement.html')

@admin.route('/announcements/<int:announcement_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_announcement(announcement_id):
    """编辑公告"""
    announcement = Announcement.query.get_or_404(announcement_id)
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            announcement.title = data.get('title', announcement.title)
            announcement.content = data.get('content', announcement.content)
            announcement.is_active = data.get('is_active', announcement.is_active)
            announcement.show_on_homepage = data.get('show_on_homepage', announcement.show_on_homepage)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '公告更新成功',
                'announcement': announcement.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    return render_template('admin/edit_announcement.html', announcement=announcement)

@admin.route('/announcements/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_announcement(announcement_id):
    """删除公告"""
    try:
        announcement = Announcement.query.get_or_404(announcement_id)
        db.session.delete(announcement)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '公告删除成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin.route('/announcements/<int:announcement_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_announcement(announcement_id):
    """切换公告状态"""
    try:
        announcement = Announcement.query.get_or_404(announcement_id)
        announcement.is_active = not announcement.is_active
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'公告已{"启用" if announcement.is_active else "禁用"}',
            'is_active': announcement.is_active
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@admin.route('/dns-rewrite', methods=['GET'])
@login_required
@admin_required
def dns_rewrite_page():
    """DNS 重写规则管理页面"""
    return render_template('admin/dns_rewrite.html')

@admin.route('/api/dns-import-sources', methods=['GET'])
@login_required
@admin_required
def get_dns_import_sources():
    """获取DNS导入源列表"""
    try:
        sources = DnsImportSource.query.order_by(DnsImportSource.last_import_time.desc()).all()
        return jsonify({
            'success': True,
            'sources': [{
                'id': source.id,
                'source_url': source.source_url,
                'last_import_time': source.last_import_time.isoformat() if source.last_import_time else None,
                'total_rules': source.total_rules,
                'success_rules': source.success_rules,
                'failed_rules': source.failed_rules,
                'status': source.status
            } for source in sources]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-import-sources/<int:source_id>/delete-rules', methods=['POST'])
@login_required
@admin_required
def delete_rules_by_source(source_id):
    """根据导入源删除相关的DNS重写规则"""
    try:
        source = DnsImportSource.query.get_or_404(source_id)
        
        if not source.rules_snapshot:
            return jsonify({'success': False, 'error': '该导入源没有规则快照，无法删除'}), 400
        
        # 从快照中获取规则并删除
        svc = AdGuardService()
        rules_to_delete = source.get_rules_snapshot()  # 使用模型方法解析JSON
        
        # 批量删除规则
        result = svc.batch_delete_rewrite_rules(rules_to_delete)
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_rewrite_batch_delete',
            target_type='dns_import_source',
            target_id=str(source_id),
            details=f'删除导入源规则：{source.source_url}，成功{result.get("success", 0)}条，失败{result.get("failed", 0)}条'
        )
        db.session.add(log)
        
        # 删除导入源记录
        db.session.delete(source)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功删除导入源及其相关规则',
            'result': result
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@admin.route('/api/dns-import-sources/<int:source_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_import_source(source_id):
    """删除导入源记录（不删除规则）"""
    try:
        source = DnsImportSource.query.get_or_404(source_id)
        
        # 记录操作日志
        log = OperationLog(
            user_id=current_user.id,
            operation_type='dns_import_source_delete',
            target_type='dns_import_source',
            target_id=str(source_id),
            details=f'删除导入源记录：{source.source_url}'
        )
        db.session.add(log)
        
        # 删除导入源记录
        db.session.delete(source)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '成功删除导入源记录'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@admin.route('/donation-config', methods=['GET', 'POST'])
@login_required
@admin_required
def donation_config():
    """捐赠配置管理页面
    
    允许管理员配置捐赠相关设置，如商户ID、接口URL、密钥等。
    """
    config = DonationConfig.get_config()
    
    if request.method == 'POST':
        try:
            # 获取表单数据
            merchant_id = request.form.get('merchant_id', '').strip()
            api_url = request.form.get('api_url', '').strip()
            api_key = request.form.get('api_key', '').strip()
            notify_url = request.form.get('notify_url', '').strip()
            return_url = request.form.get('return_url', '').strip()
            donation_title = request.form.get('donation_title', '').strip()
            donation_description = request.form.get('donation_description', '').strip()
            min_amount = float(request.form.get('min_amount', 1.0))
            max_amount = float(request.form.get('max_amount', 10000.0))
            enabled = 'enabled' in request.form
            show_ranking = 'show_ranking' in request.form
            hide_amount = 'hide_amount' in request.form
            
            # 更新配置
            config.merchant_id = merchant_id
            config.api_url = api_url
            config.api_key = api_key
            config.notify_url = notify_url
            config.return_url = return_url
            config.donation_title = donation_title
            config.donation_description = donation_description
            config.min_amount = min_amount
            config.max_amount = max_amount
            config.enabled = enabled
            config.show_ranking = show_ranking
            config.hide_amount = hide_amount
            
            db.session.commit()
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_donation_config',
                target_type='SYSTEM',
                target_id='donation_config',
                details=f'更新捐赠配置：启用={enabled}，排行榜显示={show_ranking}，隐藏金额={hide_amount}，商户ID={merchant_id}'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('捐赠配置已更新', 'success')
            return redirect(url_for('admin.donation_config'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败：{str(e)}', 'error')
    
    return render_template('admin/donation_config.html', config=config)


@admin.route('/api/donation-config', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_donation_config():
    """管理捐赠配置API"""
    if request.method == 'GET':
        try:
            config = DonationConfig.get_config()
            return jsonify({
                'success': True,
                'config': {
                    'merchant_id': config.merchant_id,
                    'api_url': config.api_url,
                    'notify_url': config.notify_url,
                    'return_url': config.return_url,
                    'donation_title': config.donation_title,
                    'donation_description': config.donation_description,
                    'min_amount': config.min_amount,
                    'max_amount': config.max_amount,
                    'enabled': config.enabled,
                    'show_ranking': config.show_ranking,
                    'hide_amount': config.hide_amount,
                    'is_complete': config.is_configured()
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
            config = DonationConfig.get_config()
            
            # 更新配置
            if 'merchant_id' in data:
                config.merchant_id = data['merchant_id'].strip()
            if 'api_url' in data:
                config.api_url = data['api_url'].strip()
            if 'api_key' in data:
                config.api_key = data['api_key'].strip()
            if 'notify_url' in data:
                config.notify_url = data['notify_url'].strip()
            if 'return_url' in data:
                config.return_url = data['return_url'].strip()
            if 'donation_title' in data:
                config.donation_title = data['donation_title'].strip()
            if 'donation_description' in data:
                config.donation_description = data['donation_description'].strip()
            if 'min_amount' in data:
                config.min_amount = float(data['min_amount'])
            if 'max_amount' in data:
                config.max_amount = float(data['max_amount'])
            if 'enabled' in data:
                config.enabled = bool(data['enabled'])
            if 'show_ranking' in data:
                config.show_ranking = bool(data['show_ranking'])
            if 'hide_amount' in data:
                config.hide_amount = bool(data['hide_amount'])
            
            db.session.commit()
            
            # 记录操作日志
            log = OperationLog(
                user_id=current_user.id,
                operation_type='update_donation_config',
                target_type='config',
                target_id='donation',
                details='更新捐赠配置信息'
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '捐赠配置已更新',
                'config': {
                    'merchant_id': config.merchant_id,
                    'api_url': config.api_url,
                    'notify_url': config.notify_url,
                    'return_url': config.return_url,
                    'donation_title': config.donation_title,
                    'donation_description': config.donation_description,
                    'min_amount': config.min_amount,
                    'max_amount': config.max_amount,
                    'enabled': config.enabled,
                    'show_ranking': config.show_ranking,
                    'hide_amount': config.hide_amount,
                    'is_complete': config.is_configured()
                }
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500