from app import db
from app.utils.timezone import beijing_time
from datetime import datetime, timedelta
import random
import string

class VerificationCode(db.Model):
    """邮箱验证码模型"""
    __tablename__ = 'verification_codes'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(6), nullable=False)
    code_type = db.Column(db.String(20), nullable=False)  # 'register', 'reset_password', etc.
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=beijing_time)

    @staticmethod
    def generate_code():
        """生成6位数字验证码"""
        return ''.join(random.choices(string.digits, k=6))

    @classmethod
    def create_code(cls, email, code_type='register', expire_minutes=10):
        """创建验证码
        
        Args:
            email: 邮箱地址
            code_type: 验证码类型
            expire_minutes: 过期时间（分钟）
            
        Returns:
            VerificationCode: 验证码实例
        """
        # 删除该邮箱的旧验证码
        cls.query.filter_by(email=email, code_type=code_type, used=False).delete()
        
        # 创建新验证码
        code = cls.generate_code()
        expires_at = datetime.now() + timedelta(minutes=expire_minutes)
        
        verification_code = cls(
            email=email,
            code=code,
            code_type=code_type,
            expires_at=expires_at
        )
        
        db.session.add(verification_code)
        db.session.commit()
        
        return verification_code

    @classmethod
    def verify_code(cls, email, code, code_type='register'):
        """验证验证码
        
        Args:
            email: 邮箱地址
            code: 验证码
            code_type: 验证码类型
            
        Returns:
            tuple: (是否验证成功, 错误信息)
        """
        verification_code = cls.query.filter_by(
            email=email,
            code=code,
            code_type=code_type,
            used=False
        ).first()
        
        if not verification_code:
            return False, '验证码不正确'
        
        if verification_code.expires_at < datetime.now():
            return False, '验证码已过期'
        
        # 标记为已使用
        verification_code.used = True
        db.session.commit()
        
        return True, '验证成功'

    def is_expired(self):
        """检查验证码是否过期"""
        return datetime.now() > self.expires_at