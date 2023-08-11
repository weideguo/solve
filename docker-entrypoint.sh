#!/bin/bash
#
# export REDIS_HOST=127.0.0.1
# export REDIS_PORT=6379
# export REDIS_PASSWORD=my_redis_passwd
#
cd /data/solve
sed -i "s|my_redis_passwd|${REDIS_PASSWORD}|g" ./conf/config.conf
if [ -n ${REDIS_HOST} ]; then      sed -i "s|host=127.0.0.1|host=${REDIS_HOST}|g" ./conf/config.conf;fi
if [ -n ${REDIS_PORT} ]; then      sed -i "s|6379|${REDIS_PORT}|g" ./conf/config.conf;fi
if [ -n ${AES_KEY} ]; then         
AES_KEY=`echo ${AES_KEY} | sed "s|&|\\\\\\&|g"`
sed -i "s|aes_key=.*|aes_key=${AES_KEY}|g" ./conf/config.conf
fi
#python bin/solve.py start 2>/dev/null
if [ ! -d logs ]; then mkdir logs; fi
python bin/solve.py start > logs/solve.out 2>logs/solve.err
