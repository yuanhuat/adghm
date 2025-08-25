from app import db
from datetime import datetime
from enum import Enum
import uuid

class PaymentStatus(Enum):
    """支付状态枚举"""
    PENDING = 'pending'  # 待支付
    PAID = 'paid'        # 已支付
    FAILED = 'failed'    # 支付失败
    CANCELLED = 'cancelled'  # 已取消
    REFUNDED = 'refunded'    # 已退款

class PaymentType(Enum):
    """支付方式枚举"""
    ALIPAY = 'alipay'    # 支付宝
    WXPAY = 'wxpay'      # 微信支付

class DonationOrder(db.Model):
    """捐赠订单模型"""
    __tablename__ = 'donation_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(64), unique=True, nullable=False, comment='订单号')
    trade_no = db.Column(db.String(64), unique=True, nullable=True, comment='第三方交易号')
    
    # 捐赠信息
    donor_name = db.Column(db.String(100), nullable=True, comment='捐赠者姓名')
    donor_email = db.Column(db.String(255), nullable=True, comment='捐赠者邮箱')
    donor_message = db.Column(db.Text, nullable=True, comment='捐赠留言')
    amount = db.Column(db.Numeric(10, 2), nullable=False, comment='捐赠金额')
    
    # 支付信息
    payment_type = db.Column(db.Enum(PaymentType), nullable=False, comment='支付方式')
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.PENDING, comment='支付状态')
    
    # 第三方支付信息
    api_trade_no = db.Column(db.String(64), nullable=True, comment='第三方订单号')
    buyer_account = db.Column(db.String(255), nullable=True, comment='买家账号')
    
    # 回调信息
    notify_data = db.Column(db.Text, nullable=True, comment='通知数据')
    
    # 时间信息
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    paid_at = db.Column(db.DateTime, nullable=True, comment='支付时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    # IP信息
    client_ip = db.Column(db.String(45), nullable=True, comment='客户端IP')
    user_agent = db.Column(db.Text, nullable=True, comment='用户代理')
    
    def __init__(self, **kwargs):
        super(DonationOrder, self).__init__(**kwargs)
        if not self.order_no:
            self.order_no = self.generate_order_no()
    
    @staticmethod
    def generate_order_no():
        """生成订单号"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_str = str(uuid.uuid4().hex)[:6].upper()
        return f'DN{timestamp}{random_str}'
    
    def __repr__(self):
        return f'<DonationOrder {self.order_no}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'trade_no': self.trade_no,
            'donor_name': self.donor_name,
            'donor_email': self.donor_email,
            'donor_message': self.donor_message,
            'amount': float(self.amount),
            'payment_type': self.payment_type.value if self.payment_type else None,
            'payment_status': self.payment_status.value if self.payment_status else None,
            'api_trade_no': self.api_trade_no,
            'buyer_account': self.buyer_account,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'client_ip': self.client_ip
        }
    
    def is_paid(self):
        """检查是否已支付"""
        return self.payment_status == PaymentStatus.PAID
    
    def can_pay(self):
        """检查是否可以支付"""
        return self.payment_status == PaymentStatus.PENDING
    
    def mark_as_paid(self, trade_no=None, buyer_account=None):
        """标记为已支付"""
        self.payment_status = PaymentStatus.PAID
        self.paid_at = datetime.utcnow()
        if trade_no:
            self.trade_no = trade_no
        if buyer_account:
            self.buyer_account = buyer_account
    
    def mark_as_failed(self):
        """标记为支付失败"""
        self.payment_status = PaymentStatus.FAILED
    
    @classmethod
    def get_by_order_no(cls, order_no):
        """根据订单号获取订单"""
        return cls.query.filter_by(order_no=order_no).first()
    
    @classmethod
    def get_by_trade_no(cls, trade_no):
        """根据第三方交易号获取订单"""
        return cls.query.filter_by(trade_no=trade_no).first()