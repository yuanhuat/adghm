#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证码功能调试脚本
用于测试删除账户验证码的生成、存储和验证逻辑
"""

import os
import sys
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.verification_code import VerificationCode
from app.services.email_service import EmailService
from app.models.user import User

def debug_verification_code():
    """调试验证码功能"""
    app = create_app()
    
    with app.app_context():
        print("=== 验证码功能调试 ===")
        
        # 1. 检查数据库表是否存在
        print("\n1. 检查数据库表...")
        try:
            # 检查verification_codes表
            from sqlalchemy import text
            result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_codes'"))
            if result.fetchone():
                print("✓ verification_codes表存在")
            else:
                print("✗ verification_codes表不存在")
                return
                
            # 检查表结构
            result = db.session.execute(text("PRAGMA table_info(verification_codes)"))
            columns = result.fetchall()
            print(f"表结构: {[col[1] for col in columns]}")
            
        except Exception as e:
            print(f"✗ 数据库检查失败: {e}")
            return
        
        # 2. 测试验证码生成
        print("\n2. 测试验证码生成...")
        test_email = "test@example.com"
        
        try:
            # 清理旧的验证码
            VerificationCode.query.filter_by(email=test_email, code_type='delete_account').delete()
            db.session.commit()
            
            # 生成新验证码
            verification_code = VerificationCode.create_code(
                email=test_email,
                code_type='delete_account',
                expire_minutes=10
            )
            
            print(f"✓ 验证码生成成功: {verification_code.code}")
            print(f"  邮箱: {verification_code.email}")
            print(f"  类型: {verification_code.code_type}")
            print(f"  过期时间: {verification_code.expires_at}")
            print(f"  是否使用: {verification_code.used}")
            
        except Exception as e:
            print(f"✗ 验证码生成失败: {e}")
            return
        
        # 3. 测试验证码验证
        print("\n3. 测试验证码验证...")
        
        # 测试正确的验证码
        try:
            is_valid, error_msg = VerificationCode.verify_code(
                email=test_email,
                code=verification_code.code,
                code_type='delete_account'
            )
            print(f"正确验证码验证结果: {is_valid}, 消息: {error_msg}")
            
        except Exception as e:
            print(f"✗ 验证码验证失败: {e}")
        
        # 重新生成验证码用于后续测试
        VerificationCode.query.filter_by(email=test_email, code_type='delete_account').delete()
        db.session.commit()
        verification_code = VerificationCode.create_code(
            email=test_email,
            code_type='delete_account',
            expire_minutes=10
        )
        
        # 测试错误的验证码
        try:
            is_valid, error_msg = VerificationCode.verify_code(
                email=test_email,
                code="999999",  # 错误的验证码
                code_type='delete_account'
            )
            print(f"错误验证码验证结果: {is_valid}, 消息: {error_msg}")
            
        except Exception as e:
            print(f"✗ 错误验证码测试失败: {e}")
        
        # 4. 测试过期验证码
        print("\n4. 测试过期验证码...")
        try:
            # 创建一个已过期的验证码
            expired_code = VerificationCode(
                email=test_email,
                code="123456",
                code_type='delete_account',
                expires_at=datetime.now() - timedelta(minutes=1),  # 1分钟前过期
                used=False
            )
            db.session.add(expired_code)
            db.session.commit()
            
            is_valid, error_msg = VerificationCode.verify_code(
                email=test_email,
                code="123456",
                code_type='delete_account'
            )
            print(f"过期验证码验证结果: {is_valid}, 消息: {error_msg}")
            
        except Exception as e:
            print(f"✗ 过期验证码测试失败: {e}")
        
        # 5. 查看数据库中的所有验证码记录
        print("\n5. 数据库中的验证码记录...")
        try:
            codes = VerificationCode.query.filter_by(email=test_email).all()
            for code in codes:
                print(f"  ID: {code.id}, 验证码: {code.code}, 类型: {code.code_type}, "
                      f"过期时间: {code.expires_at}, 已使用: {code.used}")
                
        except Exception as e:
            print(f"✗ 查询验证码记录失败: {e}")
        
        # 6. 测试EmailService的验证方法
        print("\n6. 测试EmailService验证方法...")
        try:
            # 重新生成一个验证码
            VerificationCode.query.filter_by(email=test_email, code_type='delete_account').delete()
            db.session.commit()
            
            verification_code = VerificationCode.create_code(
                email=test_email,
                code_type='delete_account',
                expire_minutes=10
            )
            
            # 使用EmailService验证
            is_valid, error_msg = EmailService.verify_email_code(
                email=test_email,
                code=verification_code.code,
                code_type='delete_account'
            )
            print(f"EmailService验证结果: {is_valid}, 消息: {error_msg}")
            
        except Exception as e:
            print(f"✗ EmailService验证失败: {e}")
        
        # 清理测试数据
        print("\n7. 清理测试数据...")
        try:
            VerificationCode.query.filter_by(email=test_email).delete()
            db.session.commit()
            print("✓ 测试数据清理完成")
            
        except Exception as e:
            print(f"✗ 清理测试数据失败: {e}")
        
        print("\n=== 调试完成 ===")

if __name__ == '__main__':
    debug_verification_code()