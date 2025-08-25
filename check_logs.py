from app import create_app, db
from app.models.payment_log import PaymentLog, PaymentLogType

app = create_app()
with app.app_context():
    # 查看最近的错误日志
    error_logs = PaymentLog.query.filter(
        PaymentLog.log_type == PaymentLogType.ERROR
    ).order_by(PaymentLog.created_at.desc()).limit(5).all()
    
    print("=== 错误日志 ===")
    for log in error_logs:
        print(f"时间: {log.created_at}")
        print(f"标题: {log.title}")
        print(f"内容: {log.content}")
        print(f"错误信息: {log.error_message}")
        print("-" * 50)
    
    # 查看最近的支付请求日志
    payment_logs = PaymentLog.query.filter(
        PaymentLog.log_type == PaymentLogType.PAYMENT_REQUEST
    ).order_by(PaymentLog.created_at.desc()).limit(3).all()
    
    print("\n=== 支付请求日志 ===")
    for log in payment_logs:
        print(f"时间: {log.created_at}")
        print(f"标题: {log.title}")
        print(f"请求数据: {log.request_data}")
        print(f"响应数据: {log.response_data}")
        print("-" * 50)