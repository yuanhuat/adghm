from app import db
from app.utils.timezone import beijing_time
from sqlalchemy import text

class DnsImportSource(db.Model):
    """DNS重写规则导入源模型
    
    用于记录从URL导入的DNS重写规则源信息，
    支持按导入源批量管理和删除规则。
    """
    __tablename__ = 'dns_import_source'

    id = db.Column(db.Integer, primary_key=True)
    
    # 导入源信息
    source_url = db.Column(db.Text, nullable=False, comment='导入源URL')
    source_name = db.Column(db.String(255), nullable=True, comment='导入源名称')
    source_description = db.Column(db.Text, nullable=True, comment='导入源描述')
    
    # 导入统计
    total_rules = db.Column(db.Integer, default=0, nullable=False, comment='总规则数')
    success_rules = db.Column(db.Integer, default=0, nullable=False, comment='成功导入规则数')
    failed_rules = db.Column(db.Integer, default=0, nullable=False, comment='失败规则数')
    
    # 规则内容快照（用于删除时匹配）
    rules_snapshot = db.Column(db.Text, nullable=True, comment='规则内容快照，JSON格式')
    
    # 状态信息
    status = db.Column(db.String(20), default='active', nullable=False, comment='状态：active/deleted')
    last_import_time = db.Column(db.DateTime, nullable=True, comment='最后导入时间')
    last_sync_at = db.Column(db.DateTime, nullable=True, comment='最后同步时间')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=beijing_time, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time, nullable=False)
    
    def __init__(self, source_url, source_name=None, source_description=None):
        """初始化导入源对象
        
        Args:
            source_url: 导入源URL
            source_name: 导入源名称
            source_description: 导入源描述
        """
        self.source_url = source_url
        self.source_name = source_name or self._extract_name_from_url(source_url)
        self.source_description = source_description
        self.status = 'active'
    
    def _extract_name_from_url(self, url):
        """从URL中提取名称
        
        Args:
            url: URL字符串
            
        Returns:
            str: 提取的名称
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            # 提取域名作为默认名称
            domain = parsed.netloc
            if domain:
                return domain
            # 如果没有域名，使用文件名
            path_parts = parsed.path.split('/')
            if path_parts:
                filename = path_parts[-1]
                if filename:
                    return filename
            return 'Unknown Source'
        except:
            return 'Unknown Source'
    
    def update_import_stats(self, total, success, failed, rules_data=None):
        """更新导入统计信息
        
        Args:
            total: 总规则数
            success: 成功规则数
            failed: 失败规则数
            rules_data: 规则数据（用于快照）
        """
        self.total_rules = total
        self.success_rules = success
        self.failed_rules = failed
        self.last_import_time = beijing_time()
        self.last_sync_at = beijing_time()
        
        if rules_data:
            import json
            self.rules_snapshot = json.dumps(rules_data, ensure_ascii=False)
    
    def get_rules_snapshot(self):
        """获取规则快照
        
        Returns:
            list: 规则列表
        """
        if self.rules_snapshot:
            try:
                import json
                return json.loads(self.rules_snapshot)
            except:
                return []
        return []
    
    def mark_as_deleted(self):
        """标记为已删除"""
        self.status = 'deleted'
        self.updated_at = beijing_time()
    
    @classmethod
    def get_active_sources(cls):
        """获取所有活跃的导入源
        
        Returns:
            list: 活跃的导入源列表
        """
        return cls.query.filter_by(status='active').order_by(cls.created_at.desc()).all()
    
    @classmethod
    def find_by_url(cls, url):
        """根据URL查找导入源
        
        Args:
            url: 导入源URL
            
        Returns:
            DnsImportSource: 导入源对象或None
        """
        return cls.query.filter_by(source_url=url, status='active').first()
    
    def to_dict(self):
        """转换为字典格式
        
        Returns:
            dict: 字典格式的数据
        """
        return {
            'id': self.id,
            'source_url': self.source_url,
            'source_name': self.source_name,
            'source_description': self.source_description,
            'total_rules': self.total_rules,
            'success_rules': self.success_rules,
            'failed_rules': self.failed_rules,
            'status': self.status,
            'last_import_time': self.last_import_time.isoformat() if self.last_import_time else None,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<DnsImportSource {self.id}: {self.source_name}>'