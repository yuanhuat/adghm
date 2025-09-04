from datetime import datetime
from app import db
from app.utils.timezone import beijing_time


class DonationRecord(db.Model):
    """捐赠记录模型
    
    存储用户的捐赠记录，用于排行榜显示
    """
    __tablename__ = 'donation_records'
    
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(100), unique=True, nullable=False, comment='订单号')
    donor_name = db.Column(db.String(100), nullable=False, comment='捐赠者姓名')
    amount = db.Column(db.Numeric(10, 2), nullable=False, comment='捐赠金额')
    payment_type = db.Column(db.String(20), nullable=False, comment='支付方式')
    trade_no = db.Column(db.String(100), comment='支付平台交易号')
    status = db.Column(db.String(20), default='pending', comment='支付状态')
    created_at = db.Column(db.DateTime, default=beijing_time, comment='创建时间')
    paid_at = db.Column(db.DateTime, comment='支付完成时间')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='用户ID（可选）')
    
    # 关联用户表
    user = db.relationship('User', backref=db.backref('donations', lazy=True))
    
    def __repr__(self):
        return f'<DonationRecord {self.order_id}: {self.donor_name} - {self.amount}>'
    
    @classmethod
    def get_leaderboard(cls, limit=50):
        """获取捐赠排行榜
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            list: 按捐赠总额排序的捐赠者列表
        """
        from sqlalchemy import func
        
        # 按捐赠者姓名分组，计算总捐赠金额和次数
        result = db.session.query(
            cls.donor_name,
            func.sum(cls.amount).label('total_amount'),
            func.count(cls.id).label('donation_count'),
            func.max(cls.paid_at).label('latest_donation')
        ).filter(
            cls.status == 'success'
        ).group_by(
            cls.donor_name
        ).order_by(
            func.sum(cls.amount).desc()
        ).limit(limit).all()
        
        return result
    
    @classmethod
    def get_recent_donations(cls, limit=10):
        """获取最近的捐赠记录
        
        Args:
            limit: 返回记录数量限制
            
        Returns:
            list: 最近的捐赠记录
        """
        return cls.query.filter(
            cls.status == 'success'
        ).order_by(
            cls.paid_at.desc()
        ).limit(limit).all()
    
    @classmethod
    def get_total_amount(cls):
        """获取总捐赠金额
        
        Returns:
            Decimal: 总捐赠金额
        """
        from sqlalchemy import func
        
        result = db.session.query(
            func.sum(cls.amount)
        ).filter(
            cls.status == 'success'
        ).scalar()
        
        return result or 0
    
    @classmethod
    def get_total_count(cls):
        """获取总捐赠次数
        
        Returns:
            int: 总捐赠次数
        """
        return cls.query.filter(
            cls.status == 'success'
        ).count()
    
    def process_vip_upgrade(self):
        """处理VIP升级逻辑
        
        当捐赠成功时调用此方法，根据VIP配置自动升级用户为VIP
        """
        if self.status != 'success' or not self.user_id:
            return
        
        from app.models.vip_config import VipConfig
        from app.models.user import User
        
        user = User.query.get(self.user_id)
        if not user:
            return
        
        # 总是增加用户累计捐赠金额（无论VIP功能是否启用）
        user.add_donation(self.amount)
        
        # 检查是否符合VIP升级条件
        vip_config = VipConfig.get_config()
        if vip_config.is_vip_eligible(self.amount):
            # 计算VIP天数并延长VIP时间
            vip_days = vip_config.calculate_vip_days(self.amount)
            if vip_days > 0:
                user.extend_vip(vip_days)
            
        db.session.commit()
    
    def to_dict(self):
        """转换为字典格式
        
        Returns:
            dict: 捐赠记录字典
        """
        return {
            'id': self.id,
            'order_id': self.order_id,
            'donor_name': self.donor_name,
            'amount': float(self.amount),
            'payment_type': self.payment_type,
            'trade_no': self.trade_no,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'user_id': self.user_id
        }