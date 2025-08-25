from app import db
from datetime import datetime
from sqlalchemy import text

class PaymentConfig(db.Model):
    """支付配置模型"""
    __tablename__ = 'payment_config'
    
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.String(50), nullable=False, comment='商户ID')
    merchant_key = db.Column(db.String(255), nullable=False, comment='商户密钥')
    api_url = db.Column(db.String(255), nullable=False, default='https://pay.mcnode.cn/mapi.php', comment='API地址')
    submit_url = db.Column(db.String(255), nullable=False, default='https://pay.mcnode.cn/submit.php', comment='提交地址')
    notify_url = db.Column(db.String(255), nullable=False, comment='异步通知地址')
    return_url = db.Column(db.String(255), nullable=False, comment='同步跳转地址')
    
    # 支付方式配置
    enable_alipay = db.Column(db.Boolean, default=True, comment='启用支付宝')
    enable_wxpay = db.Column(db.Boolean, default=True, comment='启用微信支付')
    
    # 金额限制
    min_amount = db.Column(db.Numeric(10, 2), default=1.00, comment='最小金额')
    max_amount = db.Column(db.Numeric(10, 2), default=10000.00, comment='最大金额')
    
    # 状态和时间
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    
    def __repr__(self):
        return f'<PaymentConfig {self.merchant_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'api_url': self.api_url,
            'submit_url': self.submit_url,
            'notify_url': self.notify_url,
            'return_url': self.return_url,
            'enable_alipay': self.enable_alipay,
            'enable_wxpay': self.enable_wxpay,
            'min_amount': float(self.min_amount),
            'max_amount': float(self.max_amount),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_active_config(cls):
        """获取当前激活的支付配置"""
        return cls.query.filter_by(is_active=True).first()