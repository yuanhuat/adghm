from flask import render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.payment import payment
from app import db
from app.models.payment_config import PaymentConfig
from app.models.donation_order import DonationOrder, PaymentType, PaymentStatus
from app.models.payment_log import PaymentLog, PaymentLogType
from app.services.payment_service import PaymentService
from decimal import Decimal
import json
import hashlib
from datetime import datetime

# 用户端路由
@payment.route('/donate')
def donate():
    """捐赠页面"""
    config = PaymentConfig.get_active_config()
    if not config:
        flash('支付功能暂未配置，请联系管理员', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('payment/donate.html', config=config)

@payment.route('/create_order', methods=['POST'])
def create_order():
    """创建捐赠订单"""
    try:
        data = request.get_json()
        
        # 验证必要参数
        amount = data.get('amount')
        payment_type = data.get('payment_type')
        donor_name = data.get('donor_name', '')
        donor_email = data.get('donor_email', '')
        donor_message = data.get('donor_message', '')
        
        if not amount or not payment_type:
            return jsonify({'success': False, 'message': '参数不完整'}), 400
        
        # 验证金额
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                return jsonify({'success': False, 'message': '金额必须大于0'}), 400
        except:
            return jsonify({'success': False, 'message': '金额格式错误'}), 400
        
        # 验证支付方式
        if payment_type not in ['alipay', 'wxpay']:
            return jsonify({'success': False, 'message': '不支持的支付方式'}), 400
        
        # 获取支付配置
        config = PaymentConfig.get_active_config()
        if not config:
            return jsonify({'success': False, 'message': '支付功能暂未配置'}), 500
        
        # 检查金额限制
        if amount < config.min_amount or amount > config.max_amount:
            return jsonify({
                'success': False, 
                'message': f'捐赠金额应在 {config.min_amount} - {config.max_amount} 元之间'
            }), 400
        
        # 检查支付方式是否启用
        if payment_type == 'alipay' and not config.enable_alipay:
            return jsonify({'success': False, 'message': '支付宝支付暂未开启'}), 400
        if payment_type == 'wxpay' and not config.enable_wxpay:
            return jsonify({'success': False, 'message': '微信支付暂未开启'}), 400
        
        # 创建订单
        order = DonationOrder(
            amount=amount,
            payment_type=PaymentType.ALIPAY if payment_type == 'alipay' else PaymentType.WXPAY,
            donor_name=donor_name,
            donor_email=donor_email,
            donor_message=donor_message,
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.add(order)
        db.session.commit()
        
        # 记录日志
        PaymentLog.create_log(
            log_type=PaymentLogType.CREATE_ORDER,
            title=f'创建捐赠订单 {order.order_no}',
            order_no=order.order_no,
            content=f'金额: {amount}元, 支付方式: {payment_type}',
            client_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        return jsonify({
            'success': True,
            'order_no': order.order_no,
            'amount': float(amount),
            'payment_type': payment_type
        })
        
    except Exception as e:
        db.session.rollback()
        PaymentLog.create_log(
            log_type=PaymentLogType.ERROR,
            title='创建订单失败',
            content=str(e),
            is_success=False,
            error_message=str(e),
            client_ip=request.remote_addr
        )
        return jsonify({'success': False, 'message': '创建订单失败，请重试'}), 500

@payment.route('/pay/<order_no>')
def pay(order_no):
    """支付页面"""
    # 检查订单号是否有效
    if not order_no or order_no == 'None' or order_no.strip() == '':
        flash('订单号无效', 'error')
        return redirect(url_for('payment.donate'))
    
    order = DonationOrder.get_by_order_no(order_no)
    
    if not order:
        flash('订单不存在', 'error')
        return redirect(url_for('payment.donate'))
    
    if not order.can_pay():
        flash('订单状态异常，无法支付', 'error')
        return redirect(url_for('payment.donate'))
    
    try:
        payment_service = PaymentService()
        result = payment_service.create_payment(order)
        
        if result['success']:
            # 记录支付请求日志
            PaymentLog.create_log(
                log_type=PaymentLogType.PAYMENT_REQUEST,
                title=f'发起支付请求 {order.order_no}',
                order_no=order.order_no,
                request_data=json.dumps(result.get('request_data', {})),
                response_data=json.dumps(result.get('response_data', {})),
                client_ip=request.remote_addr
            )
            
            # 根据返回结果处理支付
            device_type = result.get('device_type', 'pc')
            
            if 'payurl' in result and result['payurl']:
                # 如果是手机端微信支付，直接跳转
                if order.payment_type == PaymentType.WXPAY and device_type == 'mobile':
                    return redirect(result['payurl'])
                # 支付宝支付，直接跳转
                elif order.payment_type == PaymentType.ALIPAY:
                    return redirect(result['payurl'])
                # PC端微信支付，显示二维码页面但提供跳转链接
                else:
                    return render_template('payment/qrcode.html', 
                                         order=order, 
                                         qrcode=result.get('qrcode'),
                                         payurl=result['payurl'],
                                         device_type=device_type)
            elif 'qrcode' in result and result['qrcode']:
                return render_template('payment/qrcode.html', 
                                     order=order, 
                                     qrcode=result['qrcode'],
                                     payurl=result.get('payurl'),
                                     device_type=device_type)
            else:
                flash('支付接口返回异常', 'error')
                return redirect(url_for('payment.donate'))
        else:
            flash(f"支付失败: {result.get('message', '未知错误')}", 'error')
            return redirect(url_for('payment.donate'))
            
    except Exception as e:
        PaymentLog.create_log(
            log_type=PaymentLogType.ERROR,
            title=f'支付请求异常 {order.order_no}',
            order_no=order.order_no,
            content=str(e),
            is_success=False,
            error_message=str(e),
            client_ip=request.remote_addr
        )
        flash('支付系统异常，请重试', 'error')
        return redirect(url_for('payment.donate'))

@payment.route('/notify', methods=['POST', 'GET'])
def notify():
    """支付异步通知"""
    try:
        # 获取通知数据
        if request.method == 'POST':
            data = request.form.to_dict()
        else:
            data = request.args.to_dict()
        
        # 记录通知日志
        PaymentLog.create_log(
            log_type=PaymentLogType.PAYMENT_NOTIFY,
            title='收到支付通知',
            content=json.dumps(data),
            client_ip=request.remote_addr
        )
        
        # 验证通知
        payment_service = PaymentService()
        if not payment_service.verify_notify(data):
            return 'FAIL', 400
        
        # 处理订单
        order_no = data.get('out_trade_no')
        trade_status = data.get('trade_status')
        trade_no = data.get('trade_no')
        
        if not order_no:
            return 'FAIL', 400
        
        order = DonationOrder.get_by_order_no(order_no)
        if not order:
            return 'FAIL', 400
        
        # 更新订单状态
        if trade_status == 'TRADE_SUCCESS' and order.can_pay():
            order.mark_as_paid(trade_no=trade_no, buyer_account=data.get('buyer', ''))
            order.notify_data = json.dumps(data)
            db.session.commit()
            
            PaymentLog.create_log(
                log_type=PaymentLogType.PAYMENT_SUCCESS,
                title=f'支付成功 {order.order_no}',
                order_no=order.order_no,
                content=f'交易号: {trade_no}, 金额: {order.amount}元',
                response_data=json.dumps(data),
                client_ip=request.remote_addr
            )
        
        return 'success'
        
    except Exception as e:
        PaymentLog.create_log(
            log_type=PaymentLogType.ERROR,
            title='处理支付通知异常',
            content=str(e),
            is_success=False,
            error_message=str(e),
            client_ip=request.remote_addr
        )
        return 'FAIL', 500

@payment.route('/return')
def return_url():
    """支付同步返回"""
    try:
        data = request.args.to_dict()
        
        # 记录返回日志
        PaymentLog.create_log(
            log_type=PaymentLogType.PAYMENT_RETURN,
            title='支付同步返回',
            content=json.dumps(data),
            client_ip=request.remote_addr
        )
        
        order_no = data.get('out_trade_no')
        trade_status = data.get('trade_status')
        
        if order_no:
            order = DonationOrder.get_by_order_no(order_no)
            if order:
                if trade_status == 'TRADE_SUCCESS':
                    flash('支付成功，感谢您的捐赠！', 'success')
                    return render_template('payment/success.html', order=order)
                else:
                    flash('支付状态异常，请联系客服', 'warning')
            else:
                flash('订单不存在', 'error')
        else:
            flash('返回参数异常', 'error')
        
        return redirect(url_for('payment.donate'))
        
    except Exception as e:
        PaymentLog.create_log(
            log_type=PaymentLogType.ERROR,
            title='处理支付返回异常',
            content=str(e),
            is_success=False,
            error_message=str(e),
            client_ip=request.remote_addr
        )
        flash('系统异常，请重试', 'error')
        return redirect(url_for('payment.donate'))

@payment.route('/check_status/<order_no>')
def check_status(order_no):
    """检查订单状态"""
    order = DonationOrder.get_by_order_no(order_no)
    if not order:
        return jsonify({'success': False, 'message': '订单不存在'})
    
    return jsonify({
        'success': True,
        'status': order.payment_status.value,
        'is_paid': order.is_paid(),
        'amount': float(order.amount),
        'created_at': order.created_at.isoformat(),
        'paid_at': order.paid_at.isoformat() if order.paid_at else None
    })

# 管理端路由
@payment.route('/admin')
@login_required
def admin_index():
    """管理端首页"""
    if not current_user.is_admin:
        flash('权限不足', 'error')
        return redirect(url_for('main.index'))
    
    # 获取统计数据
    total_orders = DonationOrder.query.count()
    paid_orders = DonationOrder.query.filter_by(payment_status=PaymentStatus.PAID).count()
    total_amount = db.session.query(db.func.sum(DonationOrder.amount)).filter_by(payment_status=PaymentStatus.PAID).scalar() or 0
    
    # 获取最近订单
    recent_orders = DonationOrder.query.order_by(DonationOrder.created_at.desc()).limit(10).all()
    
    # 获取最近日志
    recent_logs = PaymentLog.get_recent_logs(limit=20)
    
    return render_template('payment/admin/index.html',
                         total_orders=total_orders,
                         paid_orders=paid_orders,
                         total_amount=float(total_amount),
                         recent_orders=recent_orders,
                         recent_logs=recent_logs)

@payment.route('/admin/config')
@login_required
def admin_config():
    """支付配置页面"""
    if not current_user.is_admin:
        flash('权限不足', 'error')
        return redirect(url_for('main.index'))
    
    config = PaymentConfig.get_active_config()
    return render_template('payment/admin/config.html', config=config)

@payment.route('/admin/config/save', methods=['POST'])
@login_required
def admin_config_save():
    """保存支付配置"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        data = request.get_json()
        
        # 验证必要参数
        required_fields = ['merchant_id', 'merchant_key', 'notify_url', 'return_url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} 不能为空'}), 400
        
        # 获取或创建配置
        config = PaymentConfig.get_active_config()
        if not config:
            config = PaymentConfig()
            db.session.add(config)
        
        # 更新配置
        config.merchant_id = data['merchant_id']
        config.merchant_key = data['merchant_key']
        config.api_url = data.get('api_url', 'https://pay.mcnode.cn/mapi.php')
        config.submit_url = data.get('submit_url', 'https://pay.mcnode.cn/submit.php')
        config.notify_url = data['notify_url']
        config.return_url = data['return_url']
        config.enable_alipay = data.get('enable_alipay', True)
        config.enable_wxpay = data.get('enable_wxpay', True)
        config.min_amount = Decimal(str(data.get('min_amount', 1.00)))
        config.max_amount = Decimal(str(data.get('max_amount', 10000.00)))
        config.is_active = data.get('is_active', True)
        
        db.session.commit()
        
        # 记录配置更新日志
        PaymentLog.create_log(
            log_type=PaymentLogType.CONFIG_UPDATE,
            title='更新支付配置',
            content=f'商户ID: {config.merchant_id}',
            client_ip=request.remote_addr
        )
        
        return jsonify({'success': True, 'message': '配置保存成功'})
        
    except Exception as e:
        db.session.rollback()
        PaymentLog.create_log(
            log_type=PaymentLogType.ERROR,
            title='保存支付配置失败',
            content=str(e),
            is_success=False,
            error_message=str(e),
            client_ip=request.remote_addr
        )
        return jsonify({'success': False, 'message': '保存失败，请重试'}), 500

@payment.route('/admin/config/test', methods=['POST'])
@login_required
def admin_config_test():
    """测试支付配置"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    try:
        data = request.get_json()
        
        # 验证必要参数
        required_fields = ['merchant_id', 'merchant_key', 'api_url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} 不能为空'}), 400
        
        # 创建临时配置进行测试
        test_config = {
            'merchant_id': data['merchant_id'],
            'merchant_key': data['merchant_key'],
            'api_url': data.get('api_url', 'https://pay.mcnode.cn/mapi.php'),
            'submit_url': data.get('submit_url', 'https://pay.mcnode.cn/submit.php')
        }
        
        # 使用PaymentService测试配置
        payment_service = PaymentService(require_config=False)
        test_result = payment_service.test_config(test_config)
        
        # 记录测试日志
        PaymentLog.create_log(
            log_type=PaymentLogType.CONFIG_UPDATE,
            title='测试支付配置',
            content=f'商户ID: {test_config["merchant_id"]}, 测试结果: {"成功" if test_result["success"] else "失败"}',
            is_success=test_result['success'],
            error_message=test_result.get('message') if not test_result['success'] else None,
            client_ip=request.remote_addr
        )
        
        return jsonify(test_result)
        
    except Exception as e:
        PaymentLog.create_log(
            log_type=PaymentLogType.ERROR,
            title='测试支付配置失败',
            content=str(e),
            is_success=False,
            error_message=str(e),
            client_ip=request.remote_addr
        )
        return jsonify({'success': False, 'message': '测试失败，请检查配置'}), 500

@payment.route('/admin/orders')
@login_required
def admin_orders():
    """订单管理页面"""
    if not current_user.is_admin:
        flash('权限不足', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    orders = DonationOrder.query.order_by(DonationOrder.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('payment/admin/orders.html', orders=orders)

@payment.route('/admin/logs')
@login_required
def admin_logs():
    """日志管理页面"""
    if not current_user.is_admin:
        flash('权限不足', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    log_type = request.args.get('type')
    per_page = 50
    
    query = PaymentLog.query
    if log_type:
        query = query.filter_by(log_type=PaymentLogType(log_type))
    
    logs = query.order_by(PaymentLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('payment/admin/logs.html', logs=logs, current_type=log_type)