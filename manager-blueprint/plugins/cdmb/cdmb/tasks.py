import json
import os
import time
import shutil
import tempfile

import docker.errors
from docker_plugin2.tasks import with_docker_client, copy_to_volume

from cloudify_rest_client import CloudifyClient


@with_docker_client()
def prepare_rest_config(client, ctx):
    volume_mountpoint = ctx.instance.runtime_properties['volume_mountpoint']
    config_dir = tempfile.mkdtemp(prefix='restservice-config-')

    ctx.download_resource_and_render(
        'components/restservice/env.jinja2',
        os.path.join(config_dir, 'env'))
    ctx.download_resource_and_render(
        'components/restservice/cloudify-rest.conf.jinja2',
        os.path.join(config_dir, 'cloudify-rest.conf'))

    with open(os.path.join(config_dir, 'rest-security.conf'), 'w') as f:
        json.dump({
            "hash_salt": "+of8JJq71FGu1vCSeq261DNe9Rx05UGTrZ79nGkw/cY=",
            "encoding_block_size": 24,
            "secret_key": "cYSOvycw7p87Z95jR6V1qqfAcb0Koxh43TOz0+KJ+/0=",
            "encoding_alphabet": "dFUBRql96EjZ0Cy4b2NOPLVzGAk3WuH",
            "encoding_min_length": 5
        }, f)

    try:
        copy_to_volume(client, volume_mountpoint, config_dir)
    finally:
        shutil.rmtree(config_dir)


@with_docker_client('source')
def prepare_database(client, ctx):
    container = client.containers.get(
        ctx.source.instance.runtime_properties['container_id'])
    for part in container.exec_run([
                'bash', '-c',
                'source /opt/manager/work/env && /opt/manager/env/bin/python /opt/create_tables_and_add_defaults.py'  # NOQA
            ], stream=True):
        ctx.logger.info(part)


@with_docker_client()
def prepare_mgmtworker_config(client, ctx):
    volume_mountpoint = ctx.instance.runtime_properties['volume_mountpoint']
    config_dir = tempfile.mkdtemp(prefix='mgmtworker-config-')

    # just using the container name available via network, not the ip
    ctx.instance.runtime_properties['rest_host'] = 'nginx'
    ctx.instance.runtime_properties['rest_port'] = 443
    ctx.instance.runtime_properties['rest_protocol'] = 'https'
    ctx.instance.runtime_properties['file_server_host'] = 'nginx'
    ctx.instance.runtime_properties['file_server_port'] = 443
    ctx.instance.runtime_properties['file_server_protocol'] = 'https'

    ctx.download_resource_and_render(
        'components/mgmtworker/env.jinja2',
        os.path.join(config_dir, 'env'))

    with open(os.path.join(config_dir, 'broker_config.json'), 'w') as f:
        json.dump({
            'broker_hostname': ctx.instance.runtime_properties[
                'rabbitmq_endpoint_ip'],
            'broker_username': 'cloudify',
            'broker_password': 'c10udify',
            'broker_vhost': '/',
            'broker_ssl_enabled': 'true',
            'broker_cert_path':
            '/etc/rabbitmq-certs/cloudify_internal_cert.pem'
        }, f)
    try:
        copy_to_volume(client, volume_mountpoint, config_dir)
    finally:
        shutil.rmtree(config_dir)


@with_docker_client()
def prepare_nginx_config(client, ctx):
    volume_mountpoint = ctx.instance.runtime_properties['volume_mountpoint']
    config_dir = tempfile.mkdtemp(prefix='nginx-config-')

    ctx.download_resource_and_render(
        'components/nginx/cloudify.conf.jinja2',
        os.path.join(config_dir, 'cloudify.conf'))

    try:
        copy_to_volume(client, volume_mountpoint, config_dir)
    finally:
        shutil.rmtree(config_dir)


def add_rabbitmq_address(ctx):
    ctx.source.instance.runtime_properties['rabbitmq_endpoint_ip'] = \
        ctx.target.instance.runtime_properties['networks'][
        'rabbitmq_network']['ip']


def add_postgres_address(ctx):
    ctx.source.instance.runtime_properties['pg_endpoint_ip'] = \
        ctx.target.instance.runtime_properties['networks'][
        'postgres_network']['ip']
    ctx.source.instance.runtime_properties['pg_endpoint_port'] = 5432


def add_restservice_address(ctx):
    ctx.source.instance.runtime_properties['restservice_ip'] = \
        ctx.target.instance.runtime_properties['networks'][
        'nginx_network']['ip']


@with_docker_client()
def prepare_rabbitmq_certs(client, ctx):
    volume_mountpoint = ctx.instance.runtime_properties['volume_mountpoint']
    volumes_config = {
        volume_mountpoint: {'bind': '/mnt/target'},
    }

    try:
        client.images.get('frapsoft/openssl')
    except docker.errors.ImageNotFound:
        client.images.pull('frapsoft/openssl')

    container = client.containers.create(
        image='frapsoft/openssl',
        name='rabbitmq_cert_writer',
        volumes=volumes_config,
        command=[
            'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', '/mnt/target/cloudify_internal_key.pem',
            '-out', '/mnt/target/cloudify_internal_cert.pem',
            '-days', '3650', '-batch', '-nodes'
        ])

    try:
        container.start()
        while True:
            time.sleep(0.1)
            container.reload()
            if container.status == 'exited':
                break
    finally:
        container.remove()


@with_docker_client()
def prepare_nginx_certs(client, ctx):
    volume_mountpoint = ctx.instance.runtime_properties['volume_mountpoint']
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write("""
[req]
distinguished_name = req_distinguished_name
x509_extensions=SAN
[ req_distinguished_name ]
commonName=nginx
[SAN]
subjectAltName=DNS:nginx
""")

    volumes_config = {
        volume_mountpoint: {'bind': '/mnt/target'},
        f.name: {'bind': '/mnt/config'}
    }
    try:
        client.images.get('frapsoft/openssl')
    except docker.errors.ImageNotFound:
        client.images.pull('frapsoft/openssl')

    container = client.containers.create(
        image='frapsoft/openssl',
        name='rabbitmq_cert_writer',
        volumes=volumes_config,
        command=[
            'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', '/mnt/target/cloudify_internal_key.pem',
            '-out', '/mnt/target/cloudify_internal_cert.pem',
            '-days', '3650', '-batch', '-nodes', '-subj', '/CN=nginx',
            '-config', '/mnt/config'
        ])

    try:
        container.start()
        while True:
            time.sleep(0.1)
            container.reload()
            if container.status == 'exited':
                break
    finally:
        container.remove()


@with_docker_client('target')
def set_provider_context_network(client, ctx):
    print ctx
    ctx.source.instance.runtime_properties['network_id'] = \
        ctx.target.instance.runtime_properties['network_id']


@with_docker_client('target')
def update_provider_context(client, ctx):
    api_container = client.containers.get(
        ctx.target.instance.runtime_properties['container_id'])
    external_network_id = ctx.source.instance.runtime_properties['network_id']

    api_addr = None
    for network in api_container.attrs['NetworkSettings']['Networks'].values():
        if network['NetworkID'] == external_network_id:
            api_addr = network['IPAddress']
            break
    else:
        raise RuntimeError('api container not connected to external network?')

    ctx.source.instance.runtime_properties['api_addr'] = api_addr

    c = CloudifyClient(api_addr, username='admin', password='admin',
                       tenant='default_tenant', port=443, trust_all=True,
                       protocol='https')

    c.manager.create_context(name='provider', context={})
