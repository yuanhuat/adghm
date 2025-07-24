import logging
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.client_mapping import ClientMapping
from app.models.operation_log import OperationLog

from app.models.feedback import Feedback
from app.models.email_config import EmailConfig
from app.models.adguard_config import AdGuardConfig
from app.models.query_log_analysis import QueryLogAnalysis, QueryLogExport
from app.services.adguard_service import AdGuardService
from app.services.email_service import EmailService

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
    feedback.updated_at = datetime.utcnow()
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



@admin.route('/access-control')
@login_required
@admin_required
def access_control():
    """访问控制页面"""
    try:
        adguard = AdGuardService()
        access_list = adguard.get_access_list()
        return render_template('admin/access_control.html', access_list=access_list)
    except Exception as e:
        flash(f'获取访问控制列表失败：{str(e)}', 'error')
        return render_template('admin/access_control.html', access_list=None)

@admin.route('/update-access-control', methods=['POST'])
@login_required
@admin_required
def update_access_control():
    """更新访问控制列表"""
    data = request.get_json()
    action = data.get('action')
    client_id = data.get('clientId')
    list_type = data.get('listType')

    try:
        adguard = AdGuardService()
        current_list = adguard.get_access_list()

        if list_type == 'allowed':
            target_list = current_list.get('allowed_clients', [])
        elif list_type == 'disallowed':
            target_list = current_list.get('disallowed_clients', [])
        else:
            return jsonify({'error': '无效的列表类型'}), 400

        if action == 'add':
            if client_id not in target_list:
                target_list.append(client_id)
        elif action == 'remove':
            if client_id in target_list:
                target_list.remove(client_id)

        if list_type == 'allowed':
            current_list['allowed_clients'] = target_list
        else:
            current_list['disallowed_clients'] = target_list

        adguard.set_access_list(
            allowed_clients=current_list.get('allowed_clients', []),
            disallowed_clients=current_list.get('disallowed_clients', []),
            blocked_hosts=current_list.get('blocked_hosts', [])
        )
        return jsonify({'message': '更新成功'})
    except Exception as e:
        return jsonify({'error': f'更新失败：{str(e)}'}), 500

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