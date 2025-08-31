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
    
    return base_data