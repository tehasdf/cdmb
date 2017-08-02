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

RUN mkdir -p /var/log/cloudify/mgmtworker
RUN mkdir /opt/mgmtworker
RUN virtualenv /opt/mgmtworker/env
COPY dev-requirements.txt /opt/dev-requirements.txt
RUN /opt/mgmtworker/env/bin/pip install -r /opt/dev-requirements.txt
RUN /opt/mgmtworker/env/bin/pip install -e /opt/cloudify-plugins-common
RUN /opt/mgmtworker/env/bin/pip install -e /opt/cloudify-agent
RUN /opt/mgmtworker/env/bin/pip install -e /opt/cloudify-manager/workflows


VOLUME /opt/mgmtworker/work

COPY ./docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["worker"]
