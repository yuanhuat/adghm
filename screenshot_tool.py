#!/usr/bin/env python3
"""
截图工具 - 为AdGuardHome管理系统生成功能截图
"""

import asyncio
import os
from playwright.async_api import async_playwright

async def take_screenshots():
    """为各个功能页面截图"""
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 设置视口大小
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # 确保截图目录存在
        os.makedirs("screenshots", exist_ok=True)
        
        # 1. 登录页面
        print("截取登录页面...")
        await page.goto("http://localhost:5000")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/01-login-page.png", full_page=True)
        
        # 2. 注册页面
        print("截取注册页面...")
        await page.goto("http://localhost:5000/register")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/02-register-page.png", full_page=True)
        
        # 3. 执行登录
        print("执行登录操作...")
        await page.goto("http://localhost:5000")
        await page.wait_for_load_state("networkidle")
        
        # 填写登录表单
        await page.fill('input[name="email"]', "admin@qq.com")
        await page.fill('input[name="password"]', "admin")
        await page.click('button[type="submit"]')
        
        # 等待登录完成
        await page.wait_for_load_state("networkidle")
        
        # 4. 用户主页
        print("截取用户主页...")
        await page.goto("http://localhost:5000")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/03-user-dashboard.png", full_page=True)
        
        # 5. 客户端管理页面
        print("截取客户端管理页面...")
        await page.goto("http://localhost:5000/clients")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/04-client-management.png", full_page=True)
        
        # 6. 管理员后台主页
        print("截取管理员后台主页...")
        await page.goto("http://localhost:5000/admin")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/05-admin-dashboard.png", full_page=True)
        
        # 7. 用户管理页面
        print("截取用户管理页面...")
        await page.goto("http://localhost:5000/admin/users")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/06-user-management.png", full_page=True)
        
        # 8. AdGuardHome配置页面
        print("截取AdGuardHome配置页面...")
        await page.goto("http://localhost:5000/admin/adguard-config")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/07-adguard-config.png", full_page=True)
        
        # 9. DNS配置页面
        print("截取DNS配置页面...")
        await page.goto("http://localhost:5000/admin/dns-config")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/08-dns-config.png", full_page=True)
        
        # 10. 查询日志页面
        print("截取查询日志页面...")
        await page.goto("http://localhost:5000/admin/query-log")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/09-query-log.png", full_page=True)
        
        # 11. 增强查询日志页面
        print("截取增强查询日志页面...")
        await page.goto("http://localhost:5000/admin/query-log-enhanced")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/10-query-log-enhanced.png", full_page=True)
        
        # 12. AI分析配置页面
        print("截取AI分析配置页面...")
        await page.goto("http://localhost:5000/admin/ai-analysis-config")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/11-ai-analysis-config.png", full_page=True)
        
        # 13. 邮件配置页面
        print("截取邮件配置页面...")
        await page.goto("http://localhost:5000/admin/email-config")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/12-email-config.png", full_page=True)
        
        # 14. 系统配置页面
        print("截取系统配置页面...")
        await page.goto("http://localhost:5000/admin/system-config")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/13-system-config.png", full_page=True)
        
        # 15. 操作日志页面
        print("截取操作日志页面...")
        await page.goto("http://localhost:5000/admin/operation-logs")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/14-operation-logs.png", full_page=True)
        
        # 16. 反馈管理页面
        print("截取反馈管理页面...")
        await page.goto("http://localhost:5000/admin/feedbacks")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/15-feedbacks.png", full_page=True)
        
        # 17. 全局阻止服务页面
        print("截取全局阻止服务页面...")
        await page.goto("http://localhost:5000/global_blocked_services")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/16-global-blocked-services.png", full_page=True)
        
        # 18. 使用指南页面
        print("截取使用指南页面...")
        await page.goto("http://localhost:5000/guide")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="screenshots/17-guide.png", full_page=True)
        
        await browser.close()
        print("所有截图完成！")

if __name__ == "__main__":
    asyncio.run(take_screenshots()) 