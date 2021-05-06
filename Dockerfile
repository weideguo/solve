# solve Dockfile
# Version 1.0

# Base images 
FROM python:3.5
LABEL maintainer="wdg(https://github.com/weideguo)"

ENV REDIS_HOST=127.0.0.1
ENV REDIS_PORT=6379
#ENV REDIS_PASSWORD=xxx
#ENV LC_ALL=en_US.UTF-8

RUN mkdir -p /data/solve

ADD ./  /data/solve/

WORKDIR /data/solve
RUN chmod 755 docker-entrypoint.sh
RUN cp docker-entrypoint.sh /usr/local/bin/

#RUN pip install -r requirements.txt ; echo "skip DEPRECATION info"
RUN pip install -r requirements.txt  --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com ; echo "skip DEPRECATION info"

CMD ["docker-entrypoint.sh"]
