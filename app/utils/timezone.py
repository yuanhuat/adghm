from datetime import datetime, timedelta

def beijing_time():
    """
    返回北京时间（UTC+8）
    
    用于数据库模型中的默认时间值，确保所有时间戳都使用北京时间
    
    Returns:
        datetime: 当前的北京时间
    """
    return datetime.utcnow() + timedelta(hours=8)