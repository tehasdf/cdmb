FROM python:2

ENV GOSU_VERSION 1.9
RUN set -x \
    && apt-get update && apt-get install -y --no-install-recommends ca-certificates wget && rm -rf /var/lib/apt/lists/* \
    && dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')" \
    && wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch" \
    && wget -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch.asc" \
    && export GNUPGHOME="$(mktemp -d)" \
    && gpg --keyserver ha.pool.sks-keyservers.net --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 \
    && gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu \
    && rm -r "$GNUPGHOME" /usr/local/bin/gosu.asc \
    && chmod +x /usr/local/bin/gosu \
    && gosu nobody true

RUN apt-get update && apt-get install -y \
    git

RUN git clone https://github.com/cloudify-cosmo/cloudify-plugins-common /opt/cloudify-plugins-common
RUN git clone https://github.com/cloudify-cosmo/cloudify-manager /opt/cloudify-manager
RUN git clone https://github.com/cloudify-cosmo/cloudify-agent /opt/cloudify-agent

RUN mkdir -p /var/log/cloudify/rest
RUN mkdir /opt/manager
RUN virtualenv /opt/manager/env
COPY rest-requirements.txt /opt/rest-requirements.txt
COPY create_tables_and_add_defaults.py /opt/create_tables_and_add_defaults.py
RUN /opt/manager/env/bin/pip install -r /opt/rest-requirements.txt
RUN /opt/manager/env/bin/pip install -e /opt/cloudify-plugins-common
RUN /opt/manager/env/bin/pip install -e /opt/cloudify-agent
RUN /opt/manager/env/bin/pip install -e /opt/cloudify-manager/workflows
RUN /opt/manager/env/bin/pip install -e /opt/cloudify-manager/rest-service
RUN /opt/manager/env/bin/pip install psycopg2


VOLUME /opt/manager/work
EXPOSE 8100

COPY ./docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["gunicorn"]
