# -*- coding: utf-8 -*-
"""
SEO配置文件
提供各页面的SEO元数据配置
"""

# 基础SEO配置
BASE_SEO = {
    'site_name': 'AdGuard Home Manager',
    'site_description': '智能DNS管理平台，提供AdGuard Home的可视化管理界面，支持广告拦截、DNS过滤、家长控制等功能',
    'site_keywords': 'AdGuard Home,DNS管理,广告拦截,网络安全,家长控制,DNS过滤,智能路由,网络防护',
    'author': 'AdGuard Home Manager Team',
    'site_url': 'https://your-domain.com',  # 需要替换为实际域名
    'twitter_site': '@adguardhome',  # 需要替换为实际Twitter账号
    'og_image': '/static/images/og-image.jpg',  # 需要添加实际图片
}

# 各页面SEO配置
PAGE_SEO = {
    'landing': {
        'title': 'AdGuard Home Manager - 智能DNS管理平台',
        'description': '专业的AdGuard Home可视化管理平台，提供简单易用的DNS管理界面，支持广告拦截、恶意软件防护、家长控制等功能。让网络管理变得更简单。',
        'keywords': 'AdGuard Home管理,DNS管理平台,广告拦截软件,网络安全工具,家长控制,DNS过滤器,智能路由管理',
        'og_type': 'website',
    },
    'about': {
        'title': '关于我们 - AdGuard Home Manager | 专业DNS管理解决方案',
        'description': '了解AdGuard Home Manager团队，我们致力于为用户提供最优秀的DNS管理体验，让网络安全变得简单高效。',
        'keywords': '关于我们,团队介绍,DNS管理专家,网络安全团队,AdGuard Home开发',
        'og_type': 'website',
    },
    'features': {
        'title': '功能特性 - AdGuard Home Manager | 全面的DNS管理功能',
        'description': '探索AdGuard Home Manager的强大功能：广告拦截、DNS过滤、家长控制、统计分析、客户端管理等。让您的网络更安全、更快速。',
        'keywords': '功能特性,广告拦截功能,DNS过滤,家长控制,网络统计,客户端管理,安全防护',
        'og_type': 'website',
    },
    'guide': {
        'title': '使用指南 - AdGuard Home Manager | 详细配置教程',
        'description': '详细的AdGuard Home Manager使用教程，包括安装配置、客户端设置、DNS配置、过滤规则管理等。快速上手，轻松管理。',
        'keywords': '使用指南,配置教程,安装指南,DNS设置,客户端配置,过滤规则,使用手册',
        'og_type': 'article',
    },
    'pricing': {
        'title': '价格方案 - AdGuard Home Manager | 灵活的服务套餐',
        'description': '查看AdGuard Home Manager的价格方案，提供免费版和专业版选择，满足个人用户和企业用户的不同需求。',
        'keywords': '价格方案,服务套餐,免费版,专业版,企业版,订阅服务,DNS管理价格',
        'og_type': 'website',
    },
    'dashboard': {
        'title': '控制面板 - AdGuard Home Manager',
        'description': 'AdGuard Home Manager控制面板，实时监控DNS查询状态，管理客户端设备，查看统计数据。',
        'keywords': '控制面板,DNS监控,客户端管理,统计数据,实时状态',
        'og_type': 'webapp',
    },
    'clients': {
        'title': '客户端管理 - AdGuard Home Manager',
        'description': '管理您的网络设备，配置个性化DNS设置，为不同设备设置不同的过滤规则和访问控制。',
        'keywords': '客户端管理,设备管理,DNS配置,过滤规则,访问控制',
        'og_type': 'webapp',
    },
    'donation': {
        'title': '支持我们 - AdGuard Home Manager | 捐赠支持',
        'description': '支持AdGuard Home Manager项目发展，您的捐赠将帮助我们持续改进产品，提供更好的服务。',
        'keywords': '捐赠支持,项目支持,开源项目,资助开发,支持我们',
        'og_type': 'website',
    },
    'android-guide': {
        'title': 'Android配置指南 - AdGuard Home Manager | Android DNS设置教程',
        'description': '详细的Android设备DNS配置教程，支持Android 9及以上版本。学习如何在Android手机和平板上配置AdGuard Home DNS，实现广告拦截和网络防护。',
        'keywords': 'Android DNS配置,Android广告拦截,私人DNS设置,DoH配置,Android网络安全,手机DNS设置,平板DNS配置',
        'og_type': 'article',
    },
    'harmonyos-guide': {
        'title': '鸿蒙OS配置指南 - AdGuard Home Manager | HarmonyOS DNS设置教程',
        'description': '详细的鸿蒙OS设备DNS配置教程，鸿蒙系统各版本均原生支持。学习如何在鸿蒙手机和平板上配置AdGuard Home DNS，支持DoT加密协议。',
        'keywords': '鸿蒙OS DNS配置,HarmonyOS广告拦截,加密DNS设置,DoT配置,鸿蒙网络安全,华为手机DNS,鸿蒙系统配置',
        'og_type': 'article',
    },
    'ios-guide': {
        'title': 'iOS配置指南 - AdGuard Home Manager | iPhone iPad DNS设置教程',
        'description': '详细的iOS设备DNS配置教程，支持iOS 14及以上版本。学习如何在iPhone和iPad上配置AdGuard Home DNS描述文件，实现广告拦截和网络防护。',
        'keywords': 'iOS DNS配置,iPhone广告拦截,iPad DNS设置,iOS描述文件,私人DNS,DoH配置,iOS网络安全,苹果设备DNS',
        'og_type': 'article',
    },
    'windows-guide': {
        'title': 'Windows配置指南 - AdGuard Home Manager | Windows DNS设置教程',
        'description': '详细的Windows系统DNS配置教程，支持Windows 11原生方式和第三方软件YogaDNS。学习如何在Windows电脑上配置AdGuard Home DNS，实现全局广告拦截。',
        'keywords': 'Windows DNS配置,Windows 11 DNS,YogaDNS配置,Windows广告拦截,DoH配置,Windows网络安全,加密DNS设置',
        'og_type': 'article',
    },
    'macos-guide': {
        'title': 'macOS配置指南 - AdGuard Home Manager | macOS DNS设置教程',
        'description': '详细的macOS系统DNS配置教程，通过描述文件轻松配置AdGuard Home DNS，享受全局广告拦截和隐私保护功能。',
        'keywords': 'macOS DNS配置,Mac广告拦截,DNS设置,macOS描述文件,Safari配置,macOS网络安全',
        'og_type': 'article',
    },
}

# 获取页面SEO配置
def get_page_seo(page_name):
    """
    获取指定页面的SEO配置
    
    Args:
        page_name (str): 页面名称
        
    Returns:
        dict: SEO配置字典
    """
    page_config = PAGE_SEO.get(page_name, {})
    
    # 合并基础配置和页面配置
    seo_config = {
        'title': page_config.get('title', BASE_SEO['site_name']),
        'description': page_config.get('description', BASE_SEO['site_description']),
        'keywords': page_config.get('keywords', BASE_SEO['site_keywords']),
        'og_type': page_config.get('og_type', 'website'),
        'site_name': BASE_SEO['site_name'],
        'author': BASE_SEO['author'],
        'site_url': BASE_SEO['site_url'],
        'twitter_site': BASE_SEO['twitter_site'],
        'og_image': BASE_SEO['og_image'],
    }
    
    return seo_config

# 生成结构化数据
def get_structured_data(page_name, **kwargs):
    """
    生成页面的结构化数据（JSON-LD）
    
    Args:
        page_name (str): 页面名称
        **kwargs: 额外参数
        
    Returns:
        dict: 结构化数据
    """
    base_data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": BASE_SEO['site_name'],
        "description": BASE_SEO['site_description'],
        "url": BASE_SEO['site_url'],
        "author": {
            "@type": "Organization",
            "name": BASE_SEO['author']
        }
    }
    
    if page_name == 'landing':
        base_data.update({
            "@type": "SoftwareApplication",
            "applicationCategory": "NetworkApplication",
            "operatingSystem": "Cross-platform",
            "offers": {
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD"
            }
        })
    elif page_name == 'about':
        base_data.update({
            "@type": "AboutPage"
        })
    elif page_name == 'guide':
        base_data.update({
            "@type": "HowTo",
            "name": "AdGuard Home Manager使用指南",
            "description": "详细的AdGuard Home Manager配置和使用教程"
        })
    elif page_name == 'android-guide':
        base_data.update({
            "@type": "HowTo",
            "name": "Android DNS配置指南",
            "description": "详细的Android设备DNS配置教程，支持Android 9及以上版本",
            "step": [
                {
                    "@type": "HowToStep",
                    "name": "打开系统设置",
                    "text": "进入手机/平板系统设置，搜索功能DNS，找到私人DNS或加密DNS功能"
                },
                {
                    "@type": "HowToStep",
                    "name": "选择私人DNS提供商",
                    "text": "选择私人DNS提供商主机名选项"
                },
                {
                    "@type": "HowToStep",
                    "name": "输入DNS地址",
                    "text": "输入AdGuard Home的DoH地址"
                }
            ]
        })
    elif page_name == 'harmonyos-guide':
        base_data.update({
            "@type": "HowTo",
            "name": "鸿蒙OS DNS配置指南",
            "description": "详细的鸿蒙OS设备DNS配置教程，鸿蒙系统各版本均原生支持",
            "step": [
                {
                    "@type": "HowToStep",
                    "name": "打开系统设置",
                    "text": "进入鸿蒙手机/平板系统设置，搜索功能DNS，找到加密DNS功能"
                },
                {
                    "@type": "HowToStep",
                    "name": "配置AdGuard Home DNS",
                    "text": "选择指定DNS加密服务并输入AdGuard Home的DNS地址"
                },
                {
                    "@type": "HowToStep",
                    "name": "验证功能生效",
                    "text": "访问测试页面验证DNS广告屏蔽功能是否生效"
                }
            ]
        })
    elif page_name == 'ios-guide':
        base_data.update({
            "@type": "HowTo",
            "name": "iOS DNS配置指南",
            "description": "详细的iOS设备DNS配置教程，支持iOS 14及以上版本",
            "step": [
                {
                    "@type": "HowToStep",
                    "name": "下载DNS描述文件",
                    "text": "在iPhone/iPad的Safari浏览器中，下载AdGuard Home DNS描述文件"
                },
                {
                    "@type": "HowToStep",
                    "name": "安装描述文件",
                    "text": "进入系统设置→通用→VPN、DNS与设备管理，找到下载的描述文件并完成安装"
                },
                {
                    "@type": "HowToStep",
                    "name": "验证功能生效",
                    "text": "访问测试页面验证AdGuard Home DNS广告拦截功能是否生效"
                }
            ]
        })
    elif page_name == 'windows-guide':
        base_data.update({
            "@type": "HowTo",
            "name": "Windows DNS配置指南",
            "description": "详细的Windows系统DNS配置教程，支持Windows 11原生方式和第三方软件YogaDNS",
            "step": [
                {
                    "@type": "HowToStep",
                    "name": "下载并安装YogaDNS软件",
                    "text": "从官网下载YogaDNS软件并完成安装，选择空白模板创建DNS服务"
                },
                {
                    "@type": "HowToStep",
                    "name": "添加18bit DNS服务",
                    "text": "在YogaDNS中添加18bit DNS服务，配置DoH协议和服务地址"
                },
                {
                    "@type": "HowToStep",
                    "name": "启动DNS服务并验证",
                    "text": "启动DNS服务并访问测试页面验证广告拦截功能是否生效"
                }
            ]
        })
    elif page_name == 'macos-guide':
        base_data.update({
            "@type": "HowTo",
            "name": "macOS DNS配置指南",
            "description": "详细的macOS系统DNS配置教程，通过描述文件轻松配置AdGuard Home DNS",
            "step": [
                {
                    "@type": "HowToStep",
                    "name": "下载DNS描述文件",
                    "text": "在Safari浏览器中下载AdGuard Home DNS描述文件"
                },
                {
                    "@type": "HowToStep",
                    "name": "安装描述文件",
                    "text": "双击描述文件并在系统偏好设置中完成安装"
                },
                {
                    "@type": "HowToStep",
                    "name": "验证配置效果",
                    "text": "访问测试页面验证DNS配置是否生效，确认广告拦截功能正常工作"
                }
            ]
        })
    
    return base_data