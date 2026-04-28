FROM python:3.13.13-slim-bookworm

# 设置时区和编码环境变量
ENV TZ=Asia/Shanghai \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    # 禁用 PIP 进度条
    PIP_PROGRESS_BAR=off \
    # 设置非交互模式，避免安装时的交互提示
    DEBIAN_FRONTEND=noninteractive

WORKDIR /data/solve

ARG INDEX_URL="https://pypi.org/simple/"
ARG TRUSTED_HOST="pypi.org"

RUN ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

RUN sed -i 's|deb.debian.org|ftp.cn.debian.org|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|security.debian.org|ftp.cn.debian.org/debian-security|g' /etc/apt/sources.list.d/debian.sources 
# 安装失败，需要privileged启动容器后再手动安装？
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#        tzdata \
#        sshpass \
#        pv && \
#    # 清理缓存，减小镜像体积
#    apt-get clean && \
#    rm -rf /var/lib/apt/lists/*

COPY requirements3.13.txt ./
RUN pip install --no-cache-dir \
    -r requirements3.13.txt \
    --index-url ${INDEX_URL} \
    --trusted-host ${TRUSTED_HOST} \
    || echo "install complete"

COPY . .

RUN cp conf/config.conf.sample conf/config.conf

RUN chmod 755 docker-entrypoint.sh && \
    ln -s /data/solve/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENV REDIS_HOST=127.0.0.1 \
    REDIS_PORT=6379
    # REDIS_PASSWORD=xxx

CMD ["docker-entrypoint.sh"]
