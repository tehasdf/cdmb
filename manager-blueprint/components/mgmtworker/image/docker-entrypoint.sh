#!/bin/bash
set -e

if [ "$1" = 'worker' ]; then
    source /opt/mgmtworker/work/env
    cd /opt/mgmtworker/work
    exec /opt/mgmtworker/env/bin/celery \
        "$@" \
        -Ofair \
        --include=cloudify.dispatch \
        --hostname cloudify.management \
        --config=cloudify.broker_config \
        --events \
        --app=cloudify_agent.app.app \
        --loglevel=${CELERY_LOG_LEVEL} \
        --queues=cloudify.management \
        --logfile=${CELERY_LOG_DIR}/cloudify.management_worker.log \
        --autoscale=10,1 \
        --without-gossip \
        --without-mingle \
        --with-gate-keeper \
        --with-logging-server \
        --logging-server-logdir=${CELERY_LOG_DIR}/logs \
        --logging-server-handler-cache-size=10
fi

if [ "$1" = 'celery' ]; then
    source /opt/mgmtworker/work/env
    cd /opt/mgmtworker/work
    exec /opt/mgmtworker/env/bin/celery \
        "${@:2}" \
        --config=cloudify.broker_config \
        --app=cloudify_agent.app.app
fi

exec "$@"
