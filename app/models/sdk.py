from datetime import datetime
import secrets
import string
from app import db
from app.utils.timezone import beijing_time


class Sdk(db.Model):
    """SDK模型
    
    用于存储SDK充值码信息，管理员可以生成SDK，用户可以使用SDK充值VIP。
    """
    __tablename__ = 'sdks'

    id = db.Column(db.Integer, primary_key=True)
    sdk_code = db.Column(db.String(32), unique=True, nullable=False, comment='SDK充值码')
    vip_days = db.Column(db.Integer, nullable=False, comment='VIP天数')
    status = db.Column(db.String(20), default='unused', nullable=False, comment='状态：unused-未使用，used-已使用，expired-已过期')
    created_at = db.Column(db.DateTime, default=beijing_time, comment='创建时间')
    used_at = db.Column(db.DateTime, nullable=True, comment='使用时间')
    used_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, comment='使用者用户ID')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='创建者用户ID')
    description = db.Column(db.String(200), nullable=True, comment='备注说明')
    
    # 关联用户表
    user = db.relationship('User', foreign_keys=[used_by], backref=db.backref('used_sdks', lazy=True))
    creator = db.relationship('User', foreign_keys=[created_by], backref=db.backref('created_sdks', lazy=True))
    
    def __init__(self, vip_days, created_by, description=None):
        """初始化SDK对象
        
        Args:
            vip_days: VIP天数
            created_by: 创建者用户ID
            description: 备注说明
        """
        self.sdk_code = self.generate_sdk_code()
        self.vip_days = vip_days
        self.created_by = created_by
        self.description = description
    
    @staticmethod
    def generate_sdk_code():
        """生成唯一的SDK充值码
        
        Returns:
            str: 32位随机字符串
        """
        while True:
            # 生成32位随机字符串，包含大小写字母和数字
            code = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
            # 检查是否已存在
            if not Sdk.query.filter_by(sdk_code=code).first():
                return code
    
    def is_valid(self):
        """检查SDK是否有效（未使用且未过期）
        
        Returns:
            bool: 是否有效
        """
        return self.status == 'unused'
    
    def use_sdk(self, user_id):
        """使用SDK
        
        Args:
            user_id: 使用者用户ID
            
        Returns:
            dict: 包含success和message的字典
        """
        if not self.is_valid():
            return {
                'success': False,
                'message': 'SDK码已失效或已被使用'
            }
        
        from app.models.user import User
        user = User.query.get(user_id)
        if not user:
            return {
                'success': False,
                'message': '用户不存在'
            }
        
        try:
            # 更新SDK状态
            self.status = 'used'
            self.used_at = beijing_time()
            self.used_by = user_id
            
            # 为用户延长VIP时间
            user.extend_vip(self.vip_days)
            
            # 记录操作日志
            from app.models.operation_log import OperationLog
            log = OperationLog(
                user_id=user_id,
                operation_type='use_sdk',
                target_type='SDK',
                target_id=str(self.id),
                details=f'使用SDK充值码：{self.sdk_code}，获得{self.vip_days}天VIP'
            )
            db.session.add(log)
            
            return {
                'success': True,
                'message': f'兑换成功！您获得了 {self.vip_days} 天VIP时长'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'兑换过程中发生错误：{str(e)}'
            }
    
    @classmethod
    def get_by_code(cls, sdk_code):
        """根据SDK码获取SDK对象
        
        Args:
            sdk_code: SDK充值码
            
        Returns:
            Sdk: SDK对象或None
        """
        return cls.query.filter_by(sdk_code=sdk_code).first()
    
    @classmethod
    def get_unused_count(cls):
        """获取未使用的SDK数量
        
        Returns:
            int: 未使用的SDK数量
        """
        return cls.query.filter_by(status='unused').count()
    
    @classmethod
    def get_used_count(cls):
        """获取已使用的SDK数量
        
        Returns:
            int: 已使用的SDK数量
        """
        return cls.query.filter_by(status='used').count()
    
    @classmethod
    def batch_create(cls, vip_days, count, created_by, description=None):
        """批量创建SDK
        
        Args:
            vip_days: VIP天数
            count: 创建数量
            created_by: 创建者用户ID
            description: 备注说明
            
        Returns:
            list: 创建的SDK对象列表
        """
        sdks = []
        for _ in range(count):
            sdk = cls(vip_days=vip_days, created_by=created_by, description=description)
            sdks.append(sdk)
            db.session.add(sdk)
        
        return sdks
    
    def to_dict(self):
        """转换为字典格式
        
        Returns:
            dict: SDK字典
        """
        return {
            'id': self.id,
            'sdk_code': self.sdk_code,
            'vip_days': self.vip_days,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'used_by': self.used_by,
            'created_by': self.created_by,
            'description': self.description
        }
    
    def __repr__(self):
        return f'<Sdk {self.sdk_code}: {self.vip_days}天 - {self.status}>'