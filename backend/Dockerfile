FROM python:3.12-slim

WORKDIR /app

# 1. 换成腾讯云源，并增加 apt 的容错能力
RUN sed -i 's/deb.debian.org/mirrors.cloud.tencent.com/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.cloud.tencent.com/g' /etc/apt/sources.list.d/debian.sources && \
    echo 'Acquire::Retries "10";' > /etc/apt/apt.conf.d/80-retries && \
    echo 'Acquire::http::Timeout "300";' >> /etc/apt/apt.conf.d/80-retries

# 2. 分开安装，每一步都清理缓存，降低内存峰值
# 第一组：最基础的构建工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl build-essential libpq-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 第二组：图像处理相关的库（这里最容易断，我们单独拉出来）
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. 安装 Python 依赖（使用清华源，比阿里源在某些地区更快）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]