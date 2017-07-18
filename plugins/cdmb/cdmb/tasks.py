import json
import os
import shutil
import tempfile
import time

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
    container.exec_run([
        'bash', '-c',
        'source /opt/manager/work/env && /opt/manager/env/bin/python /opt/create_tables_and_add_defaults.py'  # NOQA
    ])


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


PREPARE_ES_CALLS = [
    (
        'http://localhost:9200/cloudify_storage',
        json.dumps({"settings": {"analysis": {"analyzer": {
            "default": {"tokenizer": "whitespace"}}}}}),
    ),
    (
        'http://localhost:9200/cloudify_storage/blueprint/_mapping',
        json.dumps({"blueprint": {"properties": {"plan": {"enabled": False}}}})
    ),
    (
        'http://localhost:9200/cloudify_storage/deployment/_mapping',
        json.dumps({
            "deployment": {
                "properties": {
                    "workflows": {"enabled": False},
                    "inputs": {"enabled": False},
                    "policy_type": {"enabled": False},
                    "policy_triggers": {"enabled": False},
                    "groups": {"enabled": False},
                    "outputs": {"enabled": False}
                }
            }
        })
    ),
    (
        'http://localhost:9200/cloudify_storage/execution/_mapping',
        json.dumps({
            "execution": {
                "properties": {
                    "parameters": {"enabled": False}
                }
            }
        })
    ),
    (
        'http://localhost:9200/cloudify_storage/node/_mapping',
        json.dumps({
            "node": {
                "_id": {"path": "id"},
                "properties": {
                    "types": {"type": "string", "index_name": "type"},
                    "properties": {"enabled": False},
                    "operations": {"enabled": False},
                    "relationships": {"enabled": False}
                }
            }
        })
    ),
    (
        'http://localhost:9200/cloudify_storage/node_instance/_mapping',
        json.dumps({
            "node_instance": {
                "_id": {"path": "id"},
                "properties": {
                    "runtime_properties": {"enabled": False}
                }
            }
        })
    ),
    (
        'http://localhost:9200/cloudify_storage/deployment_modification'
        '/_mapping',
        json.dumps({
            "deployment_modification": {
                "_id": {"path": "id"},
                "properties": {
                    "modified_nodes": {"enabled": False},
                    "node_instances": {"enabled": False},
                    "context": {"enabled": False}
                }
            }
        })
    ),
    (
        'http://localhost:9200/cloudify_storage/deployment_update/_mapping',
        json.dumps({
            "deployment_update": {
                "_id": {"path": "id"},
                "properties": {
                    "deployment_update_nodes": {"enabled": False},
                    "deployment_update_node_instances": {"enabled": False},
                    "deployment_update_deployment": {"enabled": False},
                    "deployment_plan": {"enabled": False}
                }
            }
        })
    )

]


@with_docker_client()
def create_es_index(client, ctx):
    host_config = client.create_host_config(
        binds={
            ctx.instance.runtime_properties['volume_mountpoint']:
            {'bind': ctx.node.properties['mount_at']},
        }
    )

    container = client.create_container(
        image='elasticsearch:1',
        name='elasticsearch_writer',
        host_config=host_config
    )
    client.start(container=container['Id'])
    for retry_num in range(30):
        exec_cmd = client.exec_create(
            container=container['Id'],
            cmd=['curl', '-Ss', 'localhost:9200']
        )
        result = client.exec_start(exec_id=exec_cmd['Id'])
        if 'Connection refused' in result:
            time.sleep(1)
            ctx.logger.info('ES not ready yet... retry {0}'.format(retry_num))
        else:
            break
    try:
        for url, data in PREPARE_ES_CALLS:
            exec_cmd = client.exec_create(
                container=container['Id'],
                cmd=['curl', '-Ss', '-XPUT', '-d', data,
                     '-H', 'Content-Type: application/json', url]
            )
            result = client.exec_start(exec_id=exec_cmd['Id'])
            ctx.logger.info(result)
    finally:
        client.stop(container['Id'])
        client.remove_container(container['Id'])
