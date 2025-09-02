from app import db
from app.utils.timezone import beijing_time


class VipConfig(db.Model):
    """VIP配置模型
    
    用于存储VIP相关的配置信息，如VIP价格、时长等。
    """
    __tablename__ = 'vip_config'

    id = db.Column(db.Integer, primary_key=True)
    vip_price = db.Column(db.Numeric(10, 2), default=30.00, nullable=False, comment='VIP年费价格')
    vip_duration_days = db.Column(db.Integer, default=365, nullable=False, comment='VIP时长（天）')
    auto_upgrade = db.Column(db.Boolean, default=True, nullable=False, comment='是否自动升级为VIP')
    min_vip_amount = db.Column(db.Numeric(10, 2), default=30.00, nullable=False, comment='成为VIP的最小捐赠金额')
    cumulative_upgrade = db.Column(db.Boolean, default=True, nullable=False, comment='是否支持累计捐赠升级VIP')
    vip_title = db.Column(db.String(100), default='VIP会员', nullable=False, comment='VIP称号')
    vip_description = db.Column(db.Text, nullable=True, comment='VIP说明')
    enabled = db.Column(db.Boolean, default=True, nullable=False, comment='是否启用VIP功能')
    created_at = db.Column(db.DateTime, default=beijing_time)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time)
    
    def __init__(self, vip_price=30.00, vip_duration_days=365, auto_upgrade=True,
                 min_vip_amount=30.00, cumulative_upgrade=True, vip_title='VIP会员',
                 vip_description=None, enabled=True):
        """初始化VIP配置对象
        
        Args:
            vip_price: VIP年费价格
            vip_duration_days: VIP时长（天）
            auto_upgrade: 是否自动升级为VIP
            min_vip_amount: 成为VIP的最小捐赠金额
            cumulative_upgrade: 是否支持累计捐赠升级VIP
            vip_title: VIP称号
            vip_description: VIP说明
            enabled: 是否启用VIP功能
        """
        self.vip_price = vip_price
        self.vip_duration_days = vip_duration_days
        self.auto_upgrade = auto_upgrade
        self.min_vip_amount = min_vip_amount
        self.cumulative_upgrade = cumulative_upgrade
        self.vip_title = vip_title
        self.vip_description = vip_description
        self.enabled = enabled

    @classmethod
    def get_config(cls):
        """获取VIP配置，如果不存在则创建默认配置
        
        Returns:
            VipConfig: VIP配置对象
        """
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config

    def calculate_vip_days(self, amount):
        """根据捐赠金额计算VIP天数
        
        Args:
            amount: 捐赠金额
            
        Returns:
            int: VIP天数
        """
        if amount < self.min_vip_amount:
            return 0
        
        # 按比例计算天数
        ratio = float(amount) / float(self.vip_price)
        return int(ratio * self.vip_duration_days)
    
    def is_vip_eligible(self, amount):
        """检查捐赠金额是否符合VIP条件
        
        Args:
            amount: 捐赠金额
            
        Returns:
            bool: 是否符合VIP条件
        """
        return self.enabled and self.auto_upgrade and amount >= self.min_vip_amount