from app import db
from app.utils.timezone import beijing_time

class Announcement(db.Model):
    """公告模型"""
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, comment='公告标题')
    content = db.Column(db.Text, nullable=False, comment='公告内容')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    show_on_homepage = db.Column(db.Boolean, default=True, comment='是否在首页显示')
    created_at = db.Column(db.DateTime, default=beijing_time, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=beijing_time, onupdate=beijing_time, comment='更新时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, comment='创建者ID')

    # 关联创建者
    creator = db.relationship('User', backref='announcements', lazy=True)

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'is_active': self.is_active,
            'show_on_homepage': self.show_on_homepage,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None,
            'created_by': self.created_by
        }

    def __repr__(self):
        return f'<Announcement {self.title}>'