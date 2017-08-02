#!/bin/bash
set -e


if [ "$1" = 'get' ]; then
    source /opt/manager/work/env
    /opt/manager/env/bin/gunicorn \
        -D \
        -b 0.0.0.0:${REST_PORT} \
        --pid /var/run/gunicorn.pid \
        manager_rest.server:app
    sleep 1
    curl -Ss http://localhost:${REST_PORT}/api/v2/${@:2}
    exec kill `cat /var/run/gunicorn.pid`
fi

if [ "$1" = 'gunicorn' ]; then
    source /opt/manager/work/env
    cd /opt/manager/work
    exec /opt/manager/env/bin/gunicorn \
    --pid /var/run/gunicorn.pid \
    -w $(($(nproc)*2+1)) \
    -b 0.0.0.0:${REST_PORT} \
    --timeout 300 manager_rest.server:app \
    --access-logfile /var/log/cloudify/rest/gunicorn-access.log
fi

exec "$@"
