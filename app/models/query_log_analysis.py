from datetime import datetime
from app import db

class QueryLogAnalysis(db.Model):
    """查询日志AI分析结果模型
    
    存储AI对DNS查询日志的分析结果，包括广告识别、威胁检测等
    """
    __tablename__ = 'query_log_analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), nullable=False, index=True)  # 域名
    analysis_type = db.Column(db.String(50), nullable=False)  # 分析类型：ad, malware, tracker等
    confidence = db.Column(db.Float, nullable=False)  # 置信度 0-1
    category = db.Column(db.String(100))  # 分类：广告、追踪器、恶意软件等
    description = db.Column(db.Text)  # AI分析描述
    recommendation = db.Column(db.String(50))  # 推荐操作：block, allow, monitor
    ai_model = db.Column(db.String(50), default='deepseek')  # 使用的AI模型
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow)  # 分析时间
    is_reviewed = db.Column(db.Boolean, default=False)  # 是否已被管理员审核
    admin_action = db.Column(db.String(50))  # 管理员采取的行动
    admin_notes = db.Column(db.Text)  # 管理员备注
    reviewed_at = db.Column(db.DateTime)  # 审核时间
    reviewed_by = db.Column(db.Integer, nullable=True)  # 审核人ID
    
    def __repr__(self):
        return f'<QueryLogAnalysis {self.domain}: {self.analysis_type}({self.confidence})>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'domain': self.domain,
            'analysis_type': self.analysis_type,
            'confidence': self.confidence,
            'category': self.category,
            'description': self.description,
            'recommendation': self.recommendation,
            'ai_model': self.ai_model,
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None,
            'is_reviewed': self.is_reviewed,
            'admin_action': self.admin_action,
            'admin_notes': self.admin_notes,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewed_by': self.reviewed_by
        }

class QueryLogExport(db.Model):
    """查询日志导出记录模型
    
    记录用户的日志导出请求和状态
    """
    __tablename__ = 'query_log_export'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)  # 用户ID
    export_type = db.Column(db.String(20), nullable=False)  # csv, json
    filters = db.Column(db.JSON)  # 导出时使用的过滤条件
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    file_path = db.Column(db.String(500))  # 生成的文件路径
    file_size = db.Column(db.Integer)  # 文件大小（字节）
    record_count = db.Column(db.Integer)  # 导出的记录数
    error_message = db.Column(db.Text)  # 错误信息
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)  # 文件过期时间
    
    def __repr__(self):
        return f'<QueryLogExport {self.id}: {self.export_type} by user {self.user_id}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'export_type': self.export_type,
            'filters': self.filters,
            'status': self.status,
            'file_size': self.file_size,
            'record_count': self.record_count,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }