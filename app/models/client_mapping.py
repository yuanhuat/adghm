import json
from app import db
from app.utils.timezone import beijing_time

class ClientMapping(db.Model):
    """AdGuardHome客户端映射模型"""
    __tablename__ = 'client_mappings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    _client_ids = db.Column('client_ids', db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=beijing_time)

    @property
    def client_ids(self):
        """获取客户端ID列表"""
        return json.loads(self._client_ids)

    @client_ids.setter
    def client_ids(self, value):
        """设置客户端ID列表"""
        self._client_ids = json.dumps(value)
        
    def to_dict(self):
        """将对象转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'client_name': self.client_name,
            'client_ids': self.client_ids,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }