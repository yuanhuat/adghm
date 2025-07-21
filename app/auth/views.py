from . import auth
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.user import User
from app.models.client_mapping import ClientMapping
from app.services.adguard_service import AdGuardService

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
                        # 创建AdGuardHome客户端，使用更安全的默认配置
                        client_name = f"user_{username}"
                        client_response = adguard.create_client(
                            name=client_name,
                            ids=['192.168.31.1'],  # 使用默认IP地址
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
                            client_ids=[]
                        )
                        db.session.add(client_mapping)
                        db.session.commit()
                        
                        # 自动登录
                        login_user(user)
                        flash('注册成功！', 'success')
                        return redirect(url_for('main.index'))
                        
                    except Exception as e:
                        db.session.rollback()
                        # 如果创建客户端失败，提示具体错误
                        login_user(user)
                        flash(f'注册成功！但创建AdGuardHome客户端失败：{str(e)}', 'warning')
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