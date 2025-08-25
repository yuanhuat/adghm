from app import db
from datetime import datetime
from enum import Enum

class PaymentLogType(Enum):
    """支付日志类型枚举"""
    CREATE_ORDER = 'create_order'      # 创建订单
    PAYMENT_REQUEST = 'payment_request'  # 发起支付请求
    PAYMENT_NOTIFY = 'payment_notify'    # 支付通知
    PAYMENT_RETURN = 'payment_return'    # 支付返回
    PAYMENT_SUCCESS = 'payment_success'  # 支付成功
    PAYMENT_FAILED = 'payment_failed'    # 支付失败
    REFUND_REQUEST = 'refund_request'    # 退款请求
    REFUND_SUCCESS = 'refund_success'    # 退款成功
    CONFIG_UPDATE = 'config_update'      # 配置更新
    ERROR = 'error'                      # 错误日志

class PaymentLog(db.Model):
    """支付日志模型"""
    __tablename__ = 'payment_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(64), nullable=True, comment='订单号')
    log_type = db.Column(db.Enum(PaymentLogType), nullable=False, comment='日志类型')
    
    # 日志内容
    title = db.Column(db.String(255), nullable=False, comment='日志标题')
    content = db.Column(db.Text, nullable=True, comment='日志内容')
    request_data = db.Column(db.Text, nullable=True, comment='请求数据')
    response_data = db.Column(db.Text, nullable=True, comment='响应数据')
    
    # 状态信息
    is_success = db.Column(db.Boolean, default=True, comment='是否成功')
    error_code = db.Column(db.String(50), nullable=True, comment='错误代码')
    error_message = db.Column(db.Text, nullable=True, comment='错误信息')
    
    # 网络信息
    client_ip = db.Column(db.String(45), nullable=True, comment='客户端IP')
    user_agent = db.Column(db.Text, nullable=True, comment='用户代理')
    
    # 时间信息
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    
    def __repr__(self):
        return f'<PaymentLog {self.log_type.value}: {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'log_type': self.log_type.value if self.log_type else None,
            'title': self.title,
            'content': self.content,
            'is_success': self.is_success,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'client_ip': self.client_ip,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def create_log(cls, log_type, title, order_no=None, content=None, 
                   request_data=None, response_data=None, is_success=True,
                   error_code=None, error_message=None, client_ip=None, user_agent=None):
        """创建支付日志"""
        log = cls(
            order_no=order_no,
            log_type=log_type,
            title=title,
            content=content,
            request_data=request_data,
            response_data=response_data,
            is_success=is_success,
            error_code=error_code,
            error_message=error_message,
            client_ip=client_ip,
            user_agent=user_agent
        )
        db.session.add(log)
        try:
            db.session.commit()
            return log
        except Exception as e:
            db.session.rollback()
            print(f"Failed to create payment log: {e}")
            return None
    
    @classmethod
    def get_order_logs(cls, order_no, limit=50):
        """获取订单相关日志"""
        return cls.query.filter_by(order_no=order_no).order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_recent_logs(cls, log_type=None, limit=100):
        """获取最近的日志"""
        query = cls.query
        if log_type:
            query = query.filter_by(log_type=log_type)
        return query.order_by(cls.created_at.desc()).limit(limit).all()
    
    @classmethod
    def get_error_logs(cls, limit=50):
        """获取错误日志"""
        return cls.query.filter_by(is_success=False).order_by(cls.created_at.desc()).limit(limit).all()