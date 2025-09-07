#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除账户功能完整流程测试脚本
用于测试验证码发送、验证和账户删除的完整流程
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.verification_code import VerificationCode
from app.services.email_service import EmailService
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_delete_account_flow():
    """测试删除账户的完整流程"""
    app = create_app()
    
    with app.app_context():
        print("=== 删除账户功能完整流程测试 ===")
        
        # 1. 创建测试用户
        print("\n1. 创建测试用户...")
        test_email = "test_delete@example.com"
        
        # 清理可能存在的测试数据
        existing_user = User.query.filter_by(email=test_email).first()
        if existing_user:
            db.session.delete(existing_user)
        
        existing_codes = VerificationCode.query.filter_by(email=test_email).all()
        for code in existing_codes:
            db.session.delete(code)
        
        db.session.commit()
        
        # 创建新用户
        test_user = User(
            username="test_delete_user",
            email=test_email,
            password_hash="dummy_hash",
            email_verified=True
        )
        db.session.add(test_user)
        db.session.commit()
        print(f"✓ 测试用户创建成功: {test_email}")
        
        # 2. 测试发送删除账户验证码
        print("\n2. 测试发送删除账户验证码...")
        try:
            success, code, error = EmailService.send_verification_code(test_email, 'delete_account')
            if success:
                print(f"✓ 验证码发送成功: {code}")
            else:
                print(f"✗ 验证码发送失败: {error}")
                return False
        except Exception as e:
            print(f"✗ 发送验证码时出错: {e}")
            return False
        
        # 3. 获取发送的验证码
        print("\n3. 获取发送的验证码...")
        verification_code = VerificationCode.query.filter_by(
            email=test_email,
            code_type='delete_account',
            used=False
        ).order_by(VerificationCode.created_at.desc()).first()
        
        if not verification_code:
            print("✗ 未找到验证码记录")
            return False
        
        print(f"✓ 找到验证码: {verification_code.code}")
        print(f"  创建时间: {verification_code.created_at}")
        print(f"  过期时间: {verification_code.expires_at}")
        print(f"  是否已使用: {verification_code.used}")
        
        # 4. 测试验证码验证（正确的验证码）
        print("\n4. 测试验证码验证（正确的验证码）...")
        success, message = VerificationCode.verify_code(
            test_email, 
            verification_code.code, 
            'delete_account'
        )
        print(f"验证结果: {success}, 消息: {message}")
        
        if not success:
            print("✗ 正确的验证码验证失败")
            return False
        
        print("✓ 验证码验证成功")
        
        # 5. 测试重复使用已验证的验证码
        print("\n5. 测试重复使用已验证的验证码...")
        success, message = VerificationCode.verify_code(
            test_email, 
            verification_code.code, 
            'delete_account'
        )
        print(f"验证结果: {success}, 消息: {message}")
        
        if success:
            print("✗ 已使用的验证码不应该验证成功")
            return False
        
        print("✓ 已使用的验证码正确被拒绝")
        
        # 6. 测试发送新的验证码
        print("\n6. 测试发送新的验证码...")
        try:
            success, new_code, error = EmailService.send_verification_code(test_email, 'delete_account')
            if success:
                print(f"✓ 新验证码发送成功: {new_code}")
            else:
                print(f"✗ 新验证码发送失败: {error}")
                return False
        except Exception as e:
            print(f"✗ 发送新验证码时出错: {e}")
            return False
        
        # 7. 获取新的验证码
        print("\n7. 获取新的验证码...")
        new_verification_code = VerificationCode.query.filter_by(
            email=test_email,
            code_type='delete_account',
            used=False
        ).order_by(VerificationCode.created_at.desc()).first()
        
        if not new_verification_code:
            print("✗ 未找到新的验证码记录")
            return False
        
        print(f"✓ 找到新验证码: {new_verification_code.code}")
        
        # 8. 测试新验证码验证
        print("\n8. 测试新验证码验证...")
        success, message = VerificationCode.verify_code(
            test_email, 
            new_verification_code.code, 
            'delete_account'
        )
        print(f"验证结果: {success}, 消息: {message}")
        
        if not success:
            print("✗ 新验证码验证失败")
            return False
        
        print("✓ 新验证码验证成功")
        
        # 9. 测试各种错误情况
        print("\n9. 测试各种错误情况...")
        
        # 9.1 错误的验证码
        print("\n9.1 测试错误的验证码...")
        success, message = VerificationCode.verify_code(
            test_email, 
            "123456", 
            'delete_account'
        )
        print(f"错误验证码结果: {success}, 消息: {message}")
        
        # 9.2 空验证码
        print("\n9.2 测试空验证码...")
        success, message = VerificationCode.verify_code(
            test_email, 
            "", 
            'delete_account'
        )
        print(f"空验证码结果: {success}, 消息: {message}")
        
        # 9.3 带空格的验证码
        print("\n9.3 测试带空格的验证码...")
        # 先发送一个新的验证码
        success, latest_code_str, error = EmailService.send_verification_code(test_email, 'delete_account')
        latest_code = VerificationCode.query.filter_by(
            email=test_email,
            code_type='delete_account',
            used=False
        ).order_by(VerificationCode.created_at.desc()).first()
        
        if latest_code:
            success, message = VerificationCode.verify_code(
                test_email, 
                f" {latest_code.code} ", 
                'delete_account'
            )
            print(f"带空格验证码结果: {success}, 消息: {message}")
        
        # 10. 清理测试数据
        print("\n10. 清理测试数据...")
        test_user = User.query.filter_by(email=test_email).first()
        if test_user:
            db.session.delete(test_user)
        
        test_codes = VerificationCode.query.filter_by(email=test_email).all()
        for code in test_codes:
            db.session.delete(code)
        
        db.session.commit()
        print("✓ 测试数据清理完成")
        
        print("\n=== 测试完成 ===")
        return True

if __name__ == "__main__":
    try:
        success = test_delete_account_flow()
        if success:
            print("\n🎉 所有测试通过！")
        else:
            print("\n❌ 测试失败！")
    except Exception as e:
        print(f"\n💥 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()