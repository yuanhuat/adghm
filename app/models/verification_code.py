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
        # 记录验证尝试的详细信息（用于调试）
        import logging
        logger = logging.getLogger(__name__)
        
        # 清理输入的验证码（去除空格和非数字字符）
        if code:
            code = ''.join(c for c in str(code) if c.isdigit())
        
        logger.info(f"验证码验证尝试: email={email}, code={code}, code_type={code_type}")
        
        # 查找所有该邮箱的验证码记录（用于调试）
        all_codes = cls.query.filter_by(
            email=email,
            code_type=code_type
        ).order_by(cls.created_at.desc()).all()
        
        logger.info(f"找到 {len(all_codes)} 条验证码记录")
        for i, vc in enumerate(all_codes):
            logger.info(f"记录{i+1}: code={vc.code}, used={vc.used}, expires_at={vc.expires_at}")
        
        # 查找匹配的未使用验证码
        verification_code = cls.query.filter_by(
            email=email,
            code=code,
            code_type=code_type,
            used=False
        ).first()
        
        if not verification_code:
            # 检查是否存在该验证码但已被使用
            used_code = cls.query.filter_by(
                email=email,
                code=code,
                code_type=code_type,
                used=True
            ).first()
            
            if used_code:
                logger.warning(f"验证码已被使用: {code}")
                return False, '验证码已被使用，请重新获取验证码'
            
            # 检查是否有未过期的验证码
            valid_codes = cls.query.filter_by(
                email=email,
                code_type=code_type,
                used=False
            ).filter(cls.expires_at > datetime.now()).all()
            
            if valid_codes:
                logger.warning(f"验证码不匹配，但存在有效验证码: {[vc.code for vc in valid_codes]}")
                return False, '验证码不正确，请检查输入的验证码'
            else:
                logger.warning(f"没有找到有效的验证码")
                return False, '验证码不正确或已过期，请重新获取验证码'
        
        # 检查验证码是否过期
        if verification_code.expires_at < datetime.now():
            logger.warning(f"验证码已过期: {code}, expires_at={verification_code.expires_at}")
            return False, '验证码已过期，请重新获取验证码'
        
        # 标记为已使用
        verification_code.used = True
        db.session.commit()
        
        logger.info(f"验证码验证成功: {code}")
        return True, '验证成功'

    def is_expired(self):
        """检查验证码是否过期"""
        return datetime.now() > self.expires_at