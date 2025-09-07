#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试验证码发送功能修复
"""

import requests
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

from app import create_app, db
from app.models.user import User

def test_verification_endpoints():
    """测试验证码发送端点"""
    
    # 首先在应用上下文中创建测试用户
    app = create_app()
    with app.app_context():
        # 清理现有测试用户
        existing_user = User.query.filter_by(email='test@example.com').first()
        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()
        
        # 创建新的测试用户
        test_user = User(
            email='test@example.com',
            username='testuser',
            email_verified=True
        )
        test_user.set_password('testpassword')
        db.session.add(test_user)
        db.session.commit()
        print("✓ 测试用户创建成功")
    
    base_url = 'http://localhost:80'
    
    # 测试数据
    test_cases = [
        {
            'name': '修改邮箱验证码',
            'url': f'{base_url}/send-verification-code-for-change',
            'data': {'type': 'email'}
        },
        {
            'name': '修改密码验证码', 
            'url': f'{base_url}/send-verification-code-for-change',
            'data': {'type': 'password'}
        }
    ]
    
    print("\n=== 验证码发送功能测试 ===")
    
    # 创建会话
    session = requests.Session()
    
    # 登录
    login_data = {
        'email': 'test@example.com',
        'password': 'testpassword'
    }
    
    try:
        login_response = session.post(f'{base_url}/login', data=login_data)
        print(f"登录状态码: {login_response.status_code}")
        
        # 检查是否成功登录（重定向到首页或返回200）
        if login_response.status_code in [200, 302]:
            print("✓ 登录成功")
            
            # 测试验证码端点
            for test_case in test_cases:
                print(f"\n测试: {test_case['name']}")
                print(f"URL: {test_case['url']}")
                
                try:
                    response = session.post(
                        test_case['url'],
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(test_case['data'])
                    )
                    
                    print(f"状态码: {response.status_code}")
                    
                    if response.headers.get('content-type', '').startswith('application/json'):
                        try:
                            result = response.json()
                            print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                            
                            if result.get('success'):
                                print("✓ 验证码发送成功")
                            else:
                                print(f"✗ 验证码发送失败: {result.get('message')}")
                                
                        except Exception as e:
                            print(f"JSON解析失败: {e}")
                            print(f"响应内容: {response.text[:200]}")
                    else:
                        print(f"非JSON响应: {response.text[:200]}")
                        
                except Exception as e:
                    print(f"请求失败: {e}")
        else:
            print(f"✗ 登录失败，状态码: {login_response.status_code}")
            print(f"响应内容: {login_response.text[:200]}")
            
    except Exception as e:
        print(f"登录请求失败: {e}")
    
    print("\n=== 测试完成 ===")
    
    # 清理测试用户
    with app.app_context():
        test_user = User.query.filter_by(email='test@example.com').first()
        if test_user:
            db.session.delete(test_user)
            db.session.commit()
            print("✓ 测试用户已清理")

if __name__ == '__main__':
    test_verification_endpoints()