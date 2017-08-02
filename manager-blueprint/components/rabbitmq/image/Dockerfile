FROM rabbitmq:management

COPY rabbitmq.config /etc/rabbitmq/rabbitmq.config
COPY definitions.json /etc/rabbitmq/definitions.json
RUN chmod a+rw -R /etc/rabbitmq
