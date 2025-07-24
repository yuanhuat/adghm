from . import auth
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.models.client_mapping import ClientMapping


from app.services.adguard_service import AdGuardService

from app.services.email_service import EmailService
import re

@auth.route('/send-verification-code', methods=['POST'])
def send_verification_code():
    """发送邮箱验证码API
    
    接收邮箱地址，发送验证码到指定邮箱。
    用于用户注册时的邮箱验证。
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求数据格式错误'}), 400
        
        email = data.get('email', '').strip()
        if not email:
            return jsonify({'success': False, 'message': '请输入邮箱地址'}), 400
        
        # 验证邮箱格式
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400
        
        # 检查邮箱是否已被注册
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': '该邮箱已被注册'}), 400
        
        # 发送验证码
        success, code, error_msg = EmailService.send_verification_code(email, 'register')
        
        if success:
            return jsonify({
                'success': True, 
                'message': '验证码已发送到您的邮箱，请查收'
            })
        else:
            return jsonify({
                'success': False, 
                'message': f'验证码发送失败：{error_msg}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'服务器错误：{str(e)}'
        }), 500

@auth.route('/check_first_user', methods=['GET'])
def check_first_user():
    """检查是否为第一个用户"""
    try:
        user_count = User.query.count()
        is_first_user = user_count == 0
        return jsonify({'is_first_user': is_first_user})
    except Exception as e:
        return jsonify({'is_first_user': False, 'error': str(e)})

@auth.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册视图
    
    处理用户注册请求，创建新用户并自动为其创建AdGuardHome客户端。
    注册成功后自动登录并重定向到主页。
    第一个注册的用户将自动成为管理员。
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        verification_code = request.form.get('verification_code')
        client_name = request.form.get('client_name', '').strip()
        
        # 自动生成用户名（6-12位数字）
        import random
        import time
        
        def generate_username():
            """生成唯一的6-12位数字用户名"""
            max_attempts = 100
            for _ in range(max_attempts):
                # 生成8位数字用户名（时间戳后6位 + 2位随机数）
                timestamp_suffix = str(int(time.time()))[-6:]
                random_suffix = str(random.randint(10, 99))
                username = timestamp_suffix + random_suffix
                
                # 检查用户名是否已存在
                if not User.query.filter_by(username=username).first():
                    return username
            
            # 如果100次尝试都失败，使用完全随机的方式
            for _ in range(max_attempts):
                username = str(random.randint(100000, 999999999999))
                if not User.query.filter_by(username=username).first():
                    return username
            
            raise Exception('无法生成唯一用户名，请稍后重试')
        
        username = generate_username()
        
        # 检查是否为第一个用户
        is_first_user = User.query.count() == 0
        
        # 表单验证
        if is_first_user:
            # 第一个用户不需要验证码
            if not email or not password or not confirm_password:
                flash('请填写所有必填字段', 'error')
                return render_template('auth/register.html')
        else:
            # 非第一个用户需要验证码和客户端名称
            if not email or not password or not confirm_password or not verification_code:
                flash('请填写所有必填字段', 'error')
                return render_template('auth/register.html')
            
            # 验证客户端名称
            if not client_name:
                flash('请填写客户端名称', 'error')
                return render_template('auth/register.html')
            
            # 验证客户端名称格式（只允许字母、数字、中文、连字符和下划线）
            if not re.match(r'^[a-zA-Z0-9\u4e00-\u9fa5_-]+$', client_name):
                flash('客户端名称只能包含字母、数字、中文、连字符和下划线', 'error')
                return render_template('auth/register.html')
            
            # 验证客户端名称长度
            if len(client_name) < 2 or len(client_name) > 20:
                flash('客户端名称长度必须在2-20个字符之间', 'error')
                return render_template('auth/register.html')
            
        # 用户名已自动生成，无需验证
        
        # 验证邮箱格式
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            flash('邮箱格式不正确', 'error')
            return render_template('auth/register.html')
            
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('auth/register.html')
            
        # 用户名唯一性已在生成时确保
        
        if User.query.filter_by(email=email).first():
            flash('邮箱已被注册', 'error')
            return render_template('auth/register.html')
        
        # 验证邮箱验证码（第一个用户跳过验证）
        if not is_first_user:
            is_valid, error_msg = EmailService.verify_email_code(email, verification_code, 'register')
            if not is_valid:
                flash(error_msg, 'error')
                return render_template('auth/register.html')
        
        # 创建新用户
        user = User(username=username, email=email)
        user.set_password(password)
        user.email_verified = True  # 验证码验证通过，标记邮箱已验证
        # 如果是第一个用户，则设置为管理员
        if is_first_user:
            user.is_admin = True
        db.session.add(user)
        
        try:
            # 先提交用户创建，获取用户ID
            db.session.commit()
            
            # 检查是否为第一个用户（管理员）
            if user.is_admin:
                # 管理员用户不需要立即创建AdGuardHome客户端
                login_user(user)
                flash('注册成功！请先在后台配置AdGuardHome设置。', 'success')
                return redirect(url_for('main.index'))
            else:
                try:
                    # 检查AdGuardHome配置是否已设置并可用
                    adguard = AdGuardService()
                    
                    # 验证配置格式
                    is_valid, error_msg = adguard.config.validate()
                    if not is_valid:
                        # 配置格式无效，提示等待管理员配置
                        login_user(user)
                        flash('注册成功！但AdGuardHome配置无效，请等待管理员完成配置后再使用。', 'warning')
                        return redirect(url_for('main.index'))
                    
                    # 检查连接和认证状态
                    if not adguard.check_connection():
                        # 无法连接或认证失败，提示等待管理员配置
                        login_user(user)
                        flash('注册成功！但无法连接到AdGuardHome服务器，请等待管理员完成配置后再使用。', 'warning')
                        return redirect(url_for('main.index'))
                    
                    try:
                        # 获取设备平台信息，用作客户端ID
                        device_info_json = request.form.get('device_info', '')
                        client_ids = ['192.168.31.1']  # 默认IP地址
                        
                        # 如果有设备平台信息，则使用设备平台和用户名组合作为客户端ID，确保唯一性
                        if device_info_json:
                            try:
                                import json
                                device_info = json.loads(device_info_json)
                                # 只使用用户名作为客户端ID
                                if device_info and len(device_info) > 0:
                                    # 只使用用户名，确保唯一性
                                    # 使用连字符替代下划线，因为AdGuardHome不接受下划线作为客户端ID
                                    client_ids = [f"{username}"]  # 只使用用户名
                                    print(f"使用用户名作为客户端ID: {client_ids[0]}")
                            except Exception as e:
                                # 如果解析失败，使用默认IP地址
                                print(f"解析设备平台信息失败: {str(e)}")
                        
                        # 如果没有设备平台信息，则只使用用户名作为客户端ID
                        if len(client_ids) == 0 or client_ids[0] == '192.168.31.1':
                            # 只使用用户名作为客户端ID，确保唯一性
                            # 使用连字符替代下划线，因为AdGuardHome不接受下划线作为客户端ID
                            client_ids = [f"{username}"]  # 只使用用户名
                            print(f"使用用户名作为客户端ID: {client_ids[0]}")
                        
                        # 创建AdGuardHome客户端，使用更安全的默认配置
                        # 获取设备型号并添加到客户端名称中
                        device_platform = "unknown"
                        if device_info_json:
                            try:
                                import json
                                device_info = json.loads(device_info_json)
                                if device_info and len(device_info) > 0:
                                    device_platform = device_info[0]
                            except Exception as e:
                                print(f"解析设备平台信息失败: {str(e)}")
                        
                        # 使用用户输入的客户端名称
                        client_display_name = client_name
                        client_response = adguard.create_client(
                            name=client_display_name,
                            ids=client_ids,  # 使用设备信息作为客户端ID
                            use_global_settings=False,  # 默认不使用全局设置，让用户可以自定义
                            filtering_enabled=True,
                            safebrowsing_enabled=True,  # 启用安全浏览
                            parental_enabled=False,
                            safe_search={  # 启用安全搜索
                                "enabled": True,
                                "bing": True,
                                "duckduckgo": True,
                                "google": True,
                                "pixabay": True,
                                "yandex": True,
                                "youtube": True
                            },
                            use_global_blocked_services=False,  # 默认不使用全局屏蔽服务设置
                            ignore_querylog=False,
                            ignore_statistics=False
                        )
                        
                        # 将客户端加入允许列表
                        try:
                            # 获取当前的访问控制列表
                            access_list = adguard._make_request('GET', '/access/list')
                            allowed_clients = access_list.get('allowed_clients', [])
                            
                            # 将新客户端ID添加到允许列表
                            if client_ids[0] not in allowed_clients:
                                allowed_clients.append(client_ids[0])
                                
                                # 更新访问控制列表
                                access_data = {
                                    'allowed_clients': allowed_clients,
                                    'disallowed_clients': access_list.get('disallowed_clients', []),
                                    'blocked_hosts': access_list.get('blocked_hosts', [])
                                }
                                adguard._make_request('POST', '/access/set', json=access_data)
                                print(f"已将客户端 {client_ids[0]} 添加到允许列表")
                        except Exception as e:
                            print(f"将客户端添加到允许列表失败: {str(e)}")
                            # 继续执行，不影响用户注册流程
                        
                        # 创建客户端映射
                        client_mapping = ClientMapping(
                            user_id=user.id,
                            client_name=client_display_name,
                            client_ids=client_ids  # 使用设备信息作为客户端ID
                        )
                        db.session.add(client_mapping)
                        
                        # 注意：域名解析功能已移除
                        
                        # 提交所有更改
                        db.session.commit()
                        
                        # 自动登录
                        login_user(user)
                        flash('注册成功！', 'success')
                        return redirect(url_for('main.index'))
                        db.session.commit()
                        login_user(user)
                        flash('注册成功！', 'success')
                        return redirect(url_for('main.index'))
                        
                    except Exception as e:
                        # 不回滚用户创建，只回滚客户端映射（如果有）
                        db.session.rollback()
                        # 重新提交用户创建，确保用户已创建成功
                        db.session.add(user)
                        db.session.commit()
                        # 如果创建客户端失败，提示具体错误
                        login_user(user)
                        error_msg = str(e)
                        # 检查是否为JSON格式错误
                        if "无法解析服务器响应" in error_msg:
                            flash('注册成功！但创建AdGuardHome客户端失败：AdGuardHome服务器返回了非预期的响应格式。请联系管理员检查AdGuardHome配置。', 'warning')
                        else:
                            flash(f'注册成功！但创建AdGuardHome客户端失败：{error_msg}', 'warning')
                        # 记录详细错误信息到控制台
                        print(f"创建AdGuardHome客户端失败：{error_msg}")
                        return redirect(url_for('main.index'))
                        
                except Exception as e:
                    # 如果发生其他错误，完全回滚
                    db.session.rollback()
                    flash(f'注册失败：{str(e)}', 'error')
                    return render_template('auth/register.html')
                
        except Exception as e:
            # 如果用户创建失败，完全回滚
            db.session.rollback()
            flash(f'注册失败：{str(e)}', 'error')
            return render_template('auth/register.html')
    
    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录视图
    
    处理用户登录请求，验证用户身份并创建登录会话。
    登录成功后重定向到主页。
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        if not email or not password:
            flash('请填写邮箱和密码', 'error')
            return render_template('auth/login.html')
            
        # 验证邮箱格式
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            flash('邮箱格式不正确', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash('邮箱或密码错误', 'error')
            return render_template('auth/login.html')
        
        login_user(user, remember=remember)
        flash('登录成功！', 'success')
        
        # 重定向到登录前的页面或默认页面
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        return redirect(next_page)
    
    return render_template('auth/login.html')

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """忘记密码视图
    
    处理忘记密码请求，发送重置密码的验证码到用户邮箱。
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('请输入邮箱地址', 'error')
            return render_template('auth/forgot_password.html')
            
        # 验证邮箱格式
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            flash('邮箱格式不正确', 'error')
            return render_template('auth/forgot_password.html')
            
        # 检查邮箱是否已注册
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('该邮箱未注册', 'error')
            return render_template('auth/forgot_password.html')
            
        # 发送重置密码验证码
        success, code, error_msg = EmailService.send_verification_code(email, 'reset_password')
        
        if success:
            flash('重置密码验证码已发送到您的邮箱，请查收', 'success')
            return redirect(url_for('auth.reset_password', email=email))
        else:
            flash(f'验证码发送失败：{error_msg}', 'error')
            return render_template('auth/forgot_password.html')
            
    return render_template('auth/forgot_password.html')

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """重置密码视图
    
    处理重置密码请求，验证验证码并更新用户密码。
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    email = request.args.get('email') or request.form.get('email')
    if not email:
        flash('缺少邮箱参数', 'error')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        verification_code = request.form.get('verification_code')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not verification_code or not new_password or not confirm_password:
            flash('请填写所有字段', 'error')
            return render_template('auth/reset_password.html', email=email)
            
        if new_password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('auth/reset_password.html', email=email)
            
        # 验证密码长度
        if len(new_password) < 6:
            flash('密码长度至少为6位', 'error')
            return render_template('auth/reset_password.html', email=email)
            
        # 验证验证码
        is_valid, error_msg = EmailService.verify_email_code(email, verification_code, 'reset_password')
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('auth/reset_password.html', email=email)
            
        # 更新用户密码
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('用户不存在', 'error')
            return redirect(url_for('auth.forgot_password'))
            
        user.set_password(new_password)
        db.session.commit()
        
        flash('密码重置成功，请使用新密码登录', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', email=email)

@auth.route('/send-verification-code-for-change', methods=['POST'])
@login_required
def send_verification_code_for_change():
    """发送更改信息验证码API
    
    为更改邮箱或密码发送验证码到当前用户邮箱。
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求数据格式错误'}), 400
            
        change_type = data.get('type', '').strip()  # 'email' 或 'password'
        if change_type not in ['email', 'password']:
            return jsonify({'success': False, 'message': '无效的更改类型'}), 400
            
        # 发送验证码到当前用户邮箱
        success, code, error_msg = EmailService.send_verification_code(
            current_user.email, 
            f'change_{change_type}'
        )
        
        if success:
            return jsonify({
                'success': True, 
                'message': '验证码已发送到您的邮箱，请查收'
            })
        else:
            return jsonify({
                'success': False, 
                'message': f'验证码发送失败：{error_msg}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'服务器错误：{str(e)}'
        }), 500

@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """更改密码视图
    
    处理用户更改密码请求，需要邮箱验证码验证。
    """
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        verification_code = request.form.get('verification_code')
        
        if not current_password or not new_password or not confirm_password or not verification_code:
            flash('请填写所有字段', 'error')
            return render_template('auth/change_password.html')
            
        # 验证当前密码
        if not current_user.check_password(current_password):
            flash('当前密码错误', 'error')
            return render_template('auth/change_password.html')
            
        if new_password != confirm_password:
            flash('两次输入的新密码不一致', 'error')
            return render_template('auth/change_password.html')
            
        # 验证密码长度
        if len(new_password) < 6:
            flash('密码长度至少为6位', 'error')
            return render_template('auth/change_password.html')
            
        # 验证验证码
        is_valid, error_msg = EmailService.verify_email_code(
            current_user.email, 
            verification_code, 
            'change_password'
        )
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('auth/change_password.html')
            
        # 更新密码
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('密码修改成功', 'success')
        return redirect(url_for('main.index'))
        
    return render_template('auth/change_password.html')

@auth.route('/change-email', methods=['GET', 'POST'])
@login_required
def change_email():
    """更改邮箱视图
    
    处理用户更改邮箱请求，需要当前邮箱验证码验证。
    """
    if request.method == 'POST':
        new_email = request.form.get('new_email')
        password = request.form.get('password')
        verification_code = request.form.get('verification_code')
        
        if not new_email or not password or not verification_code:
            flash('请填写所有字段', 'error')
            return render_template('auth/change_email.html')
            
        # 验证邮箱格式
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, new_email):
            flash('新邮箱格式不正确', 'error')
            return render_template('auth/change_email.html')
            
        # 验证密码
        if not current_user.check_password(password):
            flash('密码错误', 'error')
            return render_template('auth/change_email.html')
            
        # 检查新邮箱是否已被使用
        if User.query.filter_by(email=new_email).first():
            flash('该邮箱已被其他用户使用', 'error')
            return render_template('auth/change_email.html')
            
        # 验证验证码（使用当前邮箱）
        is_valid, error_msg = EmailService.verify_email_code(
            current_user.email, 
            verification_code, 
            'change_email'
        )
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('auth/change_email.html')
            
        # 更新邮箱
        current_user.email = new_email
        current_user.email_verified = True
        db.session.commit()
        
        flash('邮箱修改成功', 'success')
        return redirect(url_for('main.index'))
        
    return render_template('auth/change_email.html')

@auth.route('/logout')
@login_required
def logout():
    """用户登出视图
    
    处理用户登出请求，清除登录会话。
    登出后重定向到登录页面。
    """
    logout_user()
    flash('您已成功登出', 'success')
    return redirect(url_for('auth.login'))