import logging
from app import create_app

app = create_app()

if __name__ == '__main__':
    # 禁用werkzeug日志输出
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='0.0.0.0', debug=True)