import json
import os
import shutil
import tempfile

from docker_plugin2.tasks import with_docker_client, copy_to_volume


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

    ctx.instance.runtime_properties['rest_host'] = 'localhost'
    ctx.instance.runtime_properties['rest_port'] = 80
    ctx.instance.runtime_properties['rest_protocol'] = 'http'
    ctx.instance.runtime_properties['file_server_host'] = 'localhost'
    ctx.instance.runtime_properties['file_server_port'] = 80
    ctx.instance.runtime_properties['file_server_protocol'] = 'http'

    ctx.download_resource_and_render(
        'components/mgmtworker/env.jinja2',
        os.path.join(config_dir, 'env'))

    with open(os.path.join(config_dir, 'broker_config.json'), 'w') as f:
        json.dump({
            'broker_hostname': ctx.instance.runtime_properties[
                'rabbitmq_endpoint_ip']
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
