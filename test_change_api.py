#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修改邮箱和密码的API功能
"""

from app import create_app
from app.models.user import User
from werkzeug.security import generate_password_hash
from app import db
import json

def test_change_apis():
    """测试修改邮箱和密码的API"""
    app = create_app()
    
    with app.app_context():
        # 创建测试客户端
        client = app.test_client()
        
        # 创建测试用户
        test_user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('password123')
        )
        db.session.add(test_user)
        db.session.commit()
        
        print("开始测试修改邮箱和密码API...")
        
        # 模拟登录状态
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        # 测试修改邮箱验证码发送
        print("\n1. 测试修改邮箱验证码发送API...")
        response1 = client.post('/auth/send-verification-code-for-change', 
                               json={'type': 'email'},
                               content_type='application/json')
        print(f"状态码: {response1.status_code}")
        print(f"响应: {response1.get_json()}")
        
        # 测试修改密码验证码发送
        print("\n2. 测试修改密码验证码发送API...")
        response2 = client.post('/auth/send-verification-code-for-change', 
                               json={'type': 'password'},
                               content_type='application/json')
        print(f"状态码: {response2.status_code}")
        print(f"响应: {response2.get_json()}")
        
        # 清理测试数据
        db.session.delete(test_user)
        db.session.commit()
        
        # 汇总结果
        print("\n=== 测试结果汇总 ===")
        success1 = response1.status_code == 200 and response1.get_json().get('success', False)
        success2 = response2.status_code == 200 and response2.get_json().get('success', False)
        
        print(f"修改邮箱API: {'✓' if success1 else '✗'}")
        print(f"修改密码API: {'✓' if success2 else '✗'}")
        print(f"\n总体结果: {'所有API测试成功！' if success1 and success2 else '部分API测试失败！'}")
        
        return success1 and success2

if __name__ == '__main__':
    test_change_apis()