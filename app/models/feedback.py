from datetime import datetime
from app import db

class Feedback(db.Model):
    """用户留言反馈模型"""
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False, comment='留言标题')
    content = db.Column(db.Text, nullable=False, comment='留言内容')
    status = db.Column(db.String(20), nullable=False, default='open', comment='留言状态：open-待处理，closed-已关闭')
    admin_reply = db.Column(db.Text, comment='管理员回复')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment='更新时间')
    closed_at = db.Column(db.DateTime, comment='关闭时间')
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='关闭人ID')
    
    # 关系
    user = db.relationship('User', foreign_keys=[user_id], backref='feedbacks')
    closed_by_user = db.relationship('User', foreign_keys=[closed_by])
    
    def __repr__(self):
        return f'<Feedback {self.id}: {self.title}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'title': self.title,
            'content': self.content,
            'status': self.status,
            'admin_reply': self.admin_reply,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'closed_by': self.closed_by,
            'closed_by_username': self.closed_by_user.username if self.closed_by_user else None
        }
    
    def close_feedback(self, admin_user_id, reply=None):
        """关闭留言"""
        self.status = 'closed'
        self.closed_at = datetime.utcnow()
        self.closed_by = admin_user_id
        if reply:
            self.admin_reply = reply
        self.updated_at = datetime.utcnow()