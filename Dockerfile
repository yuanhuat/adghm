# 使用官方 Python 作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制要求文件
COPY requirements.txt ./

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 公开容器的5000端口
EXPOSE 5000

# 运行应用
CMD ["python", "run.py"]