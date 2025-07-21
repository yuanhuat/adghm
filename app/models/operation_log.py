from datetime import datetime
from app import db

class OperationLog(db.Model):
    """操作日志模型"""
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    operation_type = db.Column(db.String(50), nullable=False)  # CREATE/UPDATE/DELETE
    target_type = db.Column(db.String(50), nullable=False)    # USER/CLIENT
    target_id = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联用户
    user = db.relationship('User', backref='operation_logs')