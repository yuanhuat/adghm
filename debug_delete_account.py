#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除账户功能调试脚本
模拟实际的删除账户流程，检查验证码验证问题
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

def debug_delete_account_flow():
    """调试删除账户完整流程"""
    app = create_app()
    
    with app.app_context():
        print("=== 删除账户功能调试 ===")
        
        test_email = "test@example.com"
        
        # 1. 清理旧数据
        print("\n1. 清理旧数据...")
        try:
            VerificationCode.query.filter_by(email=test_email).delete()
            db.session.commit()
            print("✓ 旧数据清理完成")
        except Exception as e:
            print(f"✗ 清理失败: {e}")
        
        # 2. 模拟发送验证码
        print("\n2. 模拟发送验证码...")
        try:
            success, code, error_msg = EmailService.send_verification_code(
                test_email, 'delete_account'
            )
            if success:
                print(f"✓ 验证码发送成功: {code}")
                generated_code = code
            else:
                print(f"✗ 验证码发送失败: {error_msg}")
                return
        except Exception as e:
            print(f"✗ 发送验证码异常: {e}")
            return
        
        # 3. 查看数据库中的验证码
        print("\n3. 查看数据库中的验证码...")
        try:
            verification_record = VerificationCode.query.filter_by(
                email=test_email, 
                code_type='delete_account',
                used=False
            ).first()
            
            if verification_record:
                print(f"✓ 找到验证码记录:")
                print(f"  ID: {verification_record.id}")
                print(f"  邮箱: {verification_record.email}")
                print(f"  验证码: '{verification_record.code}'")
                print(f"  验证码类型: '{verification_record.code_type}'")
                print(f"  验证码长度: {len(verification_record.code)}")
                print(f"  验证码类型: {type(verification_record.code)}")
                print(f"  过期时间: {verification_record.expires_at}")
                print(f"  是否已使用: {verification_record.used}")
                print(f"  创建时间: {verification_record.created_at}")
            else:
                print("✗ 未找到验证码记录")
                return
        except Exception as e:
            print(f"✗ 查询验证码记录失败: {e}")
            return
        
        # 4. 模拟用户输入验证码（各种情况）
        print("\n4. 模拟用户输入验证码验证...")
        
        test_cases = [
            (generated_code, "正确的验证码"),
            (str(generated_code), "字符串形式的验证码"),
            (generated_code.strip(), "去除空格的验证码"),
            (f" {generated_code} ", "带前后空格的验证码"),
            ("123456", "错误的验证码"),
            ("", "空验证码"),
            (None, "None验证码")
        ]
        
        for test_code, description in test_cases:
            try:
                print(f"\n  测试: {description}")
                print(f"  输入值: '{test_code}' (类型: {type(test_code)})")
                
                if test_code is not None:
                    print(f"  输入长度: {len(str(test_code))}")
                
                # 模拟前端处理（去除非数字字符）
                if test_code is not None:
                    processed_code = ''.join(c for c in str(test_code) if c.isdigit())
                    print(f"  前端处理后: '{processed_code}'")
                else:
                    processed_code = test_code
                
                # 验证码验证
                is_valid, error_msg = EmailService.verify_email_code(
                    test_email, processed_code, 'delete_account'
                )
                print(f"  验证结果: {is_valid}, 消息: {error_msg}")
                
                # 如果验证成功，重新生成验证码用于下一次测试
                if is_valid:
                    VerificationCode.query.filter_by(email=test_email, code_type='delete_account').delete()
                    db.session.commit()
                    success, code, error_msg = EmailService.send_verification_code(
                        test_email, 'delete_account'
                    )
                    if success:
                        generated_code = code
                        print(f"  重新生成验证码: {generated_code}")
                
            except Exception as e:
                print(f"  ✗ 测试异常: {e}")
        
        # 5. 检查验证码字符串比较
        print("\n5. 检查验证码字符串比较...")
        try:
            # 获取当前数据库中的验证码
            verification_record = VerificationCode.query.filter_by(
                email=test_email, 
                code_type='delete_account',
                used=False
            ).first()
            
            if verification_record:
                db_code = verification_record.code
                print(f"数据库中的验证码: '{db_code}' (类型: {type(db_code)})")
                
                # 测试各种比较方式
                test_input = str(generated_code)
                print(f"测试输入: '{test_input}' (类型: {type(test_input)})")
                
                print(f"直接比较: {db_code == test_input}")
                print(f"字符串比较: {str(db_code) == str(test_input)}")
                print(f"去空格比较: {str(db_code).strip() == str(test_input).strip()}")
                
                # 检查是否有隐藏字符
                print(f"数据库验证码字节: {repr(db_code)}")
                print(f"测试输入字节: {repr(test_input)}")
                
        except Exception as e:
            print(f"✗ 字符串比较测试失败: {e}")
        
        # 6. 测试直接数据库查询
        print("\n6. 测试直接数据库查询...")
        try:
            from sqlalchemy import text
            
            # 查询所有相关记录
            result = db.session.execute(text(
                "SELECT id, email, code, code_type, expires_at, used FROM verification_codes WHERE email = :email AND code_type = :code_type"
            ), {'email': test_email, 'code_type': 'delete_account'})
            
            records = result.fetchall()
            print(f"找到 {len(records)} 条记录:")
            for record in records:
                print(f"  ID: {record[0]}, 验证码: '{record[2]}', 过期时间: {record[4]}, 已使用: {record[5]}")
                
                # 测试直接SQL查询验证
                test_code = str(generated_code)
                sql_result = db.session.execute(text(
                    "SELECT COUNT(*) FROM verification_codes WHERE email = :email AND code = :code AND code_type = :code_type AND used = 0 AND expires_at > :now"
                ), {
                    'email': test_email, 
                    'code': test_code, 
                    'code_type': 'delete_account',
                    'now': datetime.now()
                })
                count = sql_result.scalar()
                print(f"  SQL直接查询结果 (code='{test_code}'): {count} 条匹配")
                
        except Exception as e:
            print(f"✗ 直接数据库查询失败: {e}")
        
        # 7. 清理测试数据
        print("\n7. 清理测试数据...")
        try:
            VerificationCode.query.filter_by(email=test_email).delete()
            db.session.commit()
            print("✓ 测试数据清理完成")
        except Exception as e:
            print(f"✗ 清理失败: {e}")
        
        print("\n=== 调试完成 ===")

if __name__ == '__main__':
    debug_delete_account_flow()