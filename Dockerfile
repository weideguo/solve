# solve Dockfile
# Version 1.0

# Base images 
FROM python:3.13
LABEL maintainer="wdg(https://github.com/weideguo)"

ARG INDEX_URL="https://pypi.org/simple/"
ARG TRUSTED_HOST="pypi.org"

ENV INDEX_URL=${INDEX_URL}
ENV TRUSTED_HOST=${TRUSTED_HOST}

ENV REDIS_HOST=127.0.0.1
ENV REDIS_PORT=6379
#ENV REDIS_PASSWORD=xxx
#ENV LC_ALL=en_US.UTF-8

#安装失败，需要privileged启动容器后在手动安装？
#RUN apt update
#RUN apt install -y sshpass pv
RUN rm /etc/localtime && ln -s /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
RUN mkdir -p /data/solve

ADD ./  /data/solve/

WORKDIR /data/solve
RUN chmod 755 docker-entrypoint.sh
RUN cp docker-entrypoint.sh /usr/local/bin/
RUN cp conf/config.conf.sample conf/config.conf

# 需要关闭进度条，否则出现安装失败？
ENV PIP_PROGRESS_BAR=off
#RUN pip install -r requirements.txt ; echo "skip DEPRECATION info"
RUN pip install -r requirements3.13.txt  --index-url ${INDEX_URL} --trusted-host ${TRUSTED_HOST} ; echo "skip DEPRECATION info"

CMD ["docker-entrypoint.sh"] 
