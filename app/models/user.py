from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from app import db, login_manager
from app.utils.timezone import beijing_time

class User(UserMixin, db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=beijing_time)
    
    # VIP相关字段
    is_vip_user = db.Column(db.Boolean, default=False, comment='是否为VIP用户')
    vip_expire_time = db.Column(db.DateTime, nullable=True, comment='VIP到期时间')
    total_donation = db.Column(db.Numeric(10, 2), default=0.00, comment='累计捐赠金额')
    
    # OpenList相关字段
    openlist_username = db.Column(db.String(100), nullable=True, comment='OpenList用户名')

    # 关联客户端映射
    client_mappings = db.relationship('ClientMapping', backref='user', lazy=True)

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def is_vip(self):
        """检查用户是否为有效VIP"""
        if not self.is_vip_user:
            return False
        if self.vip_expire_time is None:
            return True  # 永久VIP
        return self.vip_expire_time > beijing_time()
    
    def get_vip_days_left(self):
        """获取VIP剩余天数"""
        if not self.is_vip():
            return 0
        if self.vip_expire_time is None:
            return -1  # 永久VIP
        delta = self.vip_expire_time - beijing_time()
        return max(0, delta.days)
    
    def extend_vip(self, days):
        """延长VIP时间"""
        current_time = beijing_time()
        if self.vip_expire_time and self.vip_expire_time > current_time:
            # 如果当前VIP未过期，在现有时间基础上延长
            self.vip_expire_time += timedelta(days=days)
        else:
            # 如果VIP已过期或首次开通，从当前时间开始计算
            self.vip_expire_time = current_time + timedelta(days=days)
        self.is_vip_user = True
    
    def add_donation(self, amount):
        """增加捐赠金额"""
        from decimal import Decimal
        if self.total_donation is None:
            self.total_donation = Decimal('0.00')
        # 确保amount是Decimal类型
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        self.total_donation += amount

@login_manager.user_loader
def load_user(id):
    """加载用户"""
    return User.query.get(int(id))