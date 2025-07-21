from . import auth
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.models.client_mapping import ClientMapping
from app.models.domain_config import DomainConfig
from app.models.domain_mapping import DomainMapping
from app.services.adguard_service import AdGuardService
from app.services.domain_service import DomainService

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
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # 表单验证
        if not username or not password or not confirm_password:
            flash('请填写所有必填字段', 'error')
            return render_template('auth/register.html')
            
        # 验证用户名是否为6-12位数字
        import re
        if not re.match(r'^\d{6,12}$', username):
            flash('用户名必须是6-12位数字', 'error')
            return render_template('auth/register.html')
            
        if password != confirm_password:
            flash('两次输入的密码不一致', 'error')
            return render_template('auth/register.html')
            
        if User.query.filter_by(username=username).first():
            flash('用户名已存在', 'error')
            return render_template('auth/register.html')
        
        # 创建新用户
        user = User(username=username)
        user.set_password(password)
        # 检查是否为第一个用户，如果是则设置为管理员
        if User.query.count() == 0:
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
                        
                        client_name = f"user_{username}-{device_platform}"
                        client_response = adguard.create_client(
                            name=client_name,
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
                        
                        # 创建客户端映射
                        client_mapping = ClientMapping(
                            user_id=user.id,
                            client_name=client_name,
                            client_ids=client_ids  # 使用设备信息作为客户端ID
                        )
                        db.session.add(client_mapping)
                        
                        # 尝试创建阿里云域名解析
                        try:
                            # 获取域名配置
                            domain_config = DomainConfig.get_config()
                            is_valid, error_msg = domain_config.validate()
                            
                            if is_valid:
                                # 创建域名服务实例
                                domain_service = DomainService()
                                
                                # 获取IP地址
                                ip_address = domain_service.get_ip_address()
                                if ip_address:
                                    # 使用客户端ID作为子域名前缀
                                    subdomain = client_ids[0]
                                    
                                    # 创建或更新域名解析记录
                                    success, record_id, full_domain = domain_service.create_or_update_subdomain(
                                        subdomain=subdomain,
                                        ip_address=ip_address
                                    )
                                    
                                    if success and record_id:
                                        # 创建域名映射记录
                                        domain_mapping = DomainMapping(
                                            user_id=user.id,
                                            subdomain=subdomain,
                                            full_domain=full_domain,
                                            record_id=record_id,
                                            ip_address=ip_address
                                        )
                                        db.session.add(domain_mapping)
                                        
                                        # 记录操作日志
                                        domain_service.log_operation(
                                            user_id=user.id,
                                            operation_type='create',
                                            target_id=record_id,
                                            details=f'创建子域名: {subdomain}, IP: {ip_address}'
                                        )
                                        
                                        # 提交所有更改
                                        db.session.commit()
                                        
                                        # 自动登录
                                        login_user(user)
                                        flash(f'注册成功！已为您创建域名 {full_domain}', 'success')
                                        return redirect(url_for('main.index'))
                                    else:
                                        # 域名解析创建失败，但AdGuardHome客户端创建成功
                                        db.session.commit()  # 提交AdGuardHome客户端创建
                                        login_user(user)
                                        flash('注册成功！但域名解析创建失败，请联系管理员。', 'warning')
                                        return redirect(url_for('main.index'))
                                else:
                                    # 无法获取IP地址
                                    db.session.commit()  # 提交AdGuardHome客户端创建
                                    login_user(user)
                                    flash('注册成功！但无法获取您的IP地址，域名解析创建失败。', 'warning')
                                    return redirect(url_for('main.index'))
                            else:
                                # 域名配置无效
                                db.session.commit()  # 提交AdGuardHome客户端创建
                                login_user(user)
                                flash(f'注册成功！但域名配置无效：{error_msg}，请联系管理员。', 'warning')
                                return redirect(url_for('main.index'))
                                
                        except Exception as e:
                            # 域名解析创建过程中出错，但AdGuardHome客户端创建成功
                            db.session.commit()  # 提交AdGuardHome客户端创建
                            login_user(user)
                            error_msg = str(e)
                            flash(f'注册成功！但域名解析创建失败：{error_msg}', 'warning')
                            print(f"创建域名解析失败：{error_msg}")
                            return redirect(url_for('main.index'))
                        
                        # 如果没有进入任何条件分支，确保提交并登录
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
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        if not username or not password:
            flash('请填写用户名和密码', 'error')
            return render_template('auth/login.html')
            
        # 验证用户名是否为6-12位数字
        import re
        if not re.match(r'^\d{6,12}$', username):
            flash('用户名必须是6-12位数字', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('用户名或密码错误', 'error')
            return render_template('auth/login.html')
        
        login_user(user, remember=remember)
        flash('登录成功！', 'success')
        
        # 重定向到登录前的页面或默认页面
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        return redirect(next_page)
    
    return render_template('auth/login.html')

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