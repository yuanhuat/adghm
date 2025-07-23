import logging
from app import create_app

class APILogFilter(logging.Filter):
    """过滤特定API请求的日志"""
    def filter(self, record):
        # 过滤掉 /api/stats 和 /api/client_ranking 的请求日志
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            if '/api/stats' in message or '/api/client_ranking' in message:
                return False
        return True

app = create_app()

if __name__ == '__main__':
    # 设置werkzeug日志级别为INFO以显示HTTP请求日志
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.INFO)
    
    # 添加自定义过滤器来隐藏特定API的日志
    api_filter = APILogFilter()
    log.addFilter(api_filter)
    
    print(f" * Running on http://localhost:5000")
    print(f" * Running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)