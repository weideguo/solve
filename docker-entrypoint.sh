#!/bin/bash
#
# export REDIS_HOST=127.0.0.1
# export REDIS_PORT=6379
# export REDIS_PASSWORD=my_redis_passwd
#
cd /data/solve
sed -i "s|my_redis_passwd|${REDIS_PASSWORD}|g" ./conf/config.conf
if [ "X${REDIS_HOST}X" != "XX" ]; then      sed -i "s|127.0.0.1|${REDIS_HOST}|g" ./conf/config.conf;fi
if [ "X${REDIS_PORT}X" != "XX" ]; then      sed -i "s|6379|${REDIS_PORT}|g" ./conf/config.conf;fi
if [ "X${AES_KEY}X" != "XX" ]; then         sed -i "s|aes_key=.*|aes_key=${AES_KEY}|g" ./conf/config.conf;fi
python bin/solve.py start 
if [ ! -d logs ]; then mkdir logs; fi
if [ ! -f logs/solve.out ]; then touch logs/solve.out; fi
tail -f logs/solve.out 
