from app import db
from app.utils.timezone import beijing_time

class DonationConfig(db.Model):
    """捐赠配置模型
    
    用于存储捐赠支付相关的配置信息，如商户ID、接口URL、密钥等。
    """
    __tablename__ = 'donation_config'

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.String(100), nullable=True, comment='商户ID')
    api_url = db.Column(db.String(255), nullable=True, comment='支付接口URL')
    api_key = db.Column(db.String(255), nullable=True, comment='API密钥')
    notify_url = db.Column(db.String(255), nullable=True, comment='异步通知URL')
    return_url = db.Column(db.String(255), nullable=True, comment='同步返回URL')
    donation_title = db.Column(db.String(100), default='支持我们', nullable=False, comment='捐赠页面标题')
    donation_description = db.Column(db.Text, nullable=True, comment='捐赠页面描述')
    min_amount = db.Column(db.Numeric(10, 2), default=1.00, nullable=False, comment='最小捐赠金额')
    max_amount = db.Column(db.Numeric(10, 2), default=1000.00, nullable=False, comment='最大捐赠金额')
    enabled = db.Column(db.Boolean, default=False, nullable=False, comment='是否启用捐赠功能')
    show_ranking = db.Column(db.Boolean, default=True, nullable=False, comment='是否在首页显示捐赠排行榜入口')
    created_at = db.Column(db.DateTime, default=beijing_time)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
    
    def __init__(self, merchant_id=None, api_url=None, api_key=None, 
                 notify_url=None, return_url=None, donation_title='支持我们',
                 donation_description=None, min_amount=1.00, max_amount=1000.00,
                 enabled=False, show_ranking=True):
        """初始化捐赠配置对象
        
        Args:
            merchant_id: 商户ID
            api_url: 支付接口URL
            api_key: API密钥
            notify_url: 异步通知URL
            return_url: 同步返回URL
            donation_title: 捐赠页面标题
            donation_description: 捐赠页面描述
            min_amount: 最小捐赠金额
            max_amount: 最大捐赠金额
            enabled: 是否启用捐赠功能
        """
        self.merchant_id = merchant_id
        self.api_url = api_url
        self.api_key = api_key
        self.notify_url = notify_url
        self.return_url = return_url
        self.donation_title = donation_title
        self.donation_description = donation_description
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.enabled = enabled
        self.show_ranking = show_ranking
    
    @classmethod
    def get_config(cls):
        """获取捐赠配置，如果不存在则创建默认配置
        
        Returns:
            DonationConfig: 捐赠配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config
    
    def is_configured(self):
        """检查捐赠功能是否已正确配置
        
        Returns:
            bool: 如果配置完整且启用则返回True
        """
        return bool(self.enabled and 
                   self.merchant_id and 
                   self.api_url and 
                   self.api_key)