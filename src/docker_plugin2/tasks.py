
from functools import wraps
import os
import time
import tempfile

import docker.errors
from docker import DockerClient
from docker.tls import TLSConfig

CONTAINER_IN_HOST_TYPE = 'docker2.using_docker_host'
CONNECTED_TO_CONTAINER = 'docker2.container_connected_to_container'
CONNECTED_TO_VOLUME = 'docker2.container_connected_to_volume'
CONNECTED_TO_NETWORK = 'docker2.container_connected_to_network'
FROM_IMAGE = 'docker2.container_from_image'


def find_relationship(rels, kind):
    return [rel for rel in rels if kind in rel.type_hierarchy]


def _make_docker_client(connkwargs):
    connkwargs = connkwargs.copy()  # we're .pop()-ping

    tls_enabled = connkwargs.pop('tls_enabled', False)

    tls_settings = connkwargs.pop('tls_settings', {})
    if tls_enabled:
        if tls_settings:
            tls = TLSConfig(**tls_settings)
        else:
            tls = True
    else:
        tls = False

    return DockerClient(tls=tls, **connkwargs)


def prepare_client(ctx, **override_connkwargs):
    connkwargs = ctx.node.properties['connection_kwargs']
    tls_enabled = ctx.node.properties['tls']
    tls_settings = ctx.node.properties['tls_settings']
    connkwargs['tls_enabled'] = tls_enabled
    connkwargs['tls_settings'] = tls_settings
    connkwargs.update(override_connkwargs)
    client = _make_docker_client(connkwargs)
    if not client.ping():
        raise RuntimeError('Docker client error')
    ctx.instance.runtime_properties['connection_kwargs'] = connkwargs


def docker_client_for_instance(instance):
    host_rels = find_relationship(instance.relationships,
                                  CONTAINER_IN_HOST_TYPE)
    if len(host_rels) != 1:
        raise RuntimeError('{0} needs one relationship to a host but has {1}'
                           .format(instance.node.name, len(host_rels)))

    host = host_rels[0].target.instance
    props = host.runtime_properties
    connkwargs = props['connection_kwargs']

    return _make_docker_client(connkwargs)


def with_docker_client(settings_from=None):
    def decorator(f):
        @wraps(f)
        def _inner(ctx, *a, **kw):
            if settings_from is None:
                instance = ctx.instance
            elif settings_from == 'source':
                instance = ctx.source.instance
            elif settings_from == 'target':
                instance = ctx.target.instance
            else:
                raise ValueError('Invalid settings_from: {0}'.format(
                                 settings_from))

            client = docker_client_for_instance(instance)
            return f(client, ctx, *a, **kw)
        return _inner
    return decorator


def _get_build_path(download_func, base_path):
    build_dir = tempfile.mkdtemp()
    try:
        files_lst = download_func(os.path.join(base_path, 'files.lst'))
    except IOError:
        files = ['Dockerfile']
    else:
        with open(files_lst) as f:
            files = [filename for filename in f if filename.strip()]

    for filename in files:
        download_func(os.path.join(base_path, filename),
                      target_path=os.path.join(build_dir, filename))
    return build_dir


@with_docker_client()
def build_image(client, ctx):
    if ctx.node.properties.get('repository'):
        tag = ctx.node.properties.get('tag') or 'latest'
        name = '{0}:{1}'.format(ctx.node.properties['repository'], tag)
        try:
            client.images.get(name)
        except docker.errors.ImageNotFound:
            ctx.logger.info('Pulling {0}:{1}'.format(name))

            image = client.images.pull(
                ctx.node.properties['repository'],
                tag=ctx.node.properties['tag'])

        ctx.instance.runtime_properties['image'] = name
    else:
        name = ctx.node.properties['image_name']
        dockerfile = ctx.node.properties['dockerfile']
        try:
            image = client.images.get(name)
        except docker.errors.ImageNotFound:
            path = _get_build_path(ctx.download_resource, dockerfile)
            image = client.images.build(path=path, tag=name, rm=True,
                                        forcerm=True)
            ctx.logger.info('Building {0} from {1}'.format(name, dockerfile))

            if not image.id:
                raise RuntimeError('Didnt build?')

            ctx.logger.info('Built {0}'.format(image.id))
        ctx.instance.runtime_properties['image'] = image.id


@with_docker_client()
def delete_image(client, ctx):
    if not ctx.node.properties.get('keep'):
        image = client.images.get(ctx.instance.runtime_properties['image'])
        image.remove()


def find_image(ctx):
    rels = find_relationship(ctx.instance.relationships, FROM_IMAGE)
    if len(rels) != 1:
        raise RuntimeError('{0} needs exactly one relationship to an Image '
                           'but has {1}'.format(ctx.node.name, len(rels)))

    return rels[0].target.instance.runtime_properties['image']


def _make_volume_details(rel):
    target_props = rel.target.node.properties
    target_runtime_props = rel.target.instance.runtime_properties
    return {
        'volume_name': target_runtime_props['volume_name'],
        'volume_mountpoint': target_runtime_props[
            'volume_mountpoint'],
        'mode': target_props['mode'],
        'mount_at': target_props['mount_at'],
    }


def _make_network_details(rel):
    target_runtime_props = rel.target.instance.runtime_properties
    return {
        'network_id': target_runtime_props['network_id'],
        'network_name': target_runtime_props['network_name'],
        'network_options': None
    }


def find_connected_nodes(ctx, kind, make_details=None):
    rels = find_relationship(ctx.instance.relationships, kind)
    return {
        rel.target.node.name:
        make_details(rel) if make_details is not None else rel
        for rel in rels
    }


def make_connected_containers_networks(client, ctx, connected_containers):
    container_details = {}
    networks = {}
    for target_name, container_rel in connected_containers.items():
        container_instance = container_rel.target.instance
        target_client = docker_client_for_instance(container_instance)
        container = target_client.containers.get(
            container_instance.runtime_properties['container_id'])

        network_name = '{0}_to_{1}'.format(ctx.node.name, target_name)

        network = target_client.networks.create(
            name=network_name
        )
        network.connect(container)
        target_ip = None
        while not target_ip:
            try:
                target_ip = container.attrs['NetworkSettings']['Networks'][
                    network_name]['IPAddress']
            except KeyError:
                pass
            time.sleep(0.1)
            container.reload()
            ctx.logger.debug('target_ip: {0}'.format(target_ip))

        container_details[target_name] = {
            'ip': target_ip,
            'net_id': network.id,
            'container_id': container.id
        }
        networks[network_name] = {
            'network_id': network.id,
            'network_name': network_name,
            'network_options': None
        }
    return container_details, networks


@with_docker_client()
def create_container(client, ctx, **override_parameters):
    image = find_image(ctx)
    volumes = find_connected_nodes(ctx, CONNECTED_TO_VOLUME,
                                   _make_volume_details)
    networks = find_connected_nodes(ctx, CONNECTED_TO_NETWORK,
                                    _make_network_details)
    connected_containers = find_connected_nodes(ctx, CONNECTED_TO_CONTAINER)
    connected_containers_details, connected_containers_networks = \
        make_connected_containers_networks(client, ctx, connected_containers)

    if set(networks) & set(connected_containers_networks):
        raise RuntimeError('Overlapping networks? {0} vs {1}'
                           .format(networks, connected_containers_networks))
    network_aliases = ctx.node.properties['network_aliases']

    networks.update(connected_containers_networks)

    volumes_config = {
        v['volume_mountpoint']: {
            'bind': v['mount_at'],
            'mode': v['mode']
        }
        for v in volumes.values()
    }

    parameters = {
        'image': image,
        'volumes': volumes_config,
        'command': ctx.node.properties['command'],
        'name': ctx.node.properties['name'],
        'ports': ctx.node.properties['port_bindings'],
        'environment': ctx.node.properties['environment']
    }
    parameters.update(ctx.node.properties['additional_create_parameters'])
    parameters.update(**override_parameters)

    container = client.containers.create(**parameters)

    for network in networks:
        if isinstance(network_aliases, dict):
            aliases = network_aliases.get(network)
        else:
            aliases = network_aliases
        if not aliases:
            aliases = [ctx.node.id]
        net = client.networks.get(network)
        net.connect(container, aliases=aliases)

    ctx.instance.runtime_properties['container_id'] = container.id
    ctx.instance.runtime_properties['networks'] = networks
    ctx.instance.runtime_properties['volumes'] = volumes
    ctx.instance.runtime_properties['image'] = image
    ctx.instance.runtime_properties['connected'] = connected_containers_details
    ctx.instance.runtime_properties['host_ip'] = ctx.instance.host_ip


@with_docker_client()
def start_container(client, ctx):
    container_id = ctx.instance.runtime_properties['container_id']
    container = client.containers.get(container_id)
    container.start()
    while container.status == 'created':
        time.sleep(0.1)
        container.reload()

    network_settings = container.attrs['NetworkSettings']['Networks']
    networks = ctx.instance.runtime_properties.get('networks', {})
    for network_name, network_details in networks.items():
        network_details['ip'] = network_settings[network_name]['IPAddress']
    ctx.instance.runtime_properties['networks'] = networks


@with_docker_client()
def stop_container(client, ctx):
    if 'container_id' in ctx.instance.runtime_properties:
        container = client.containers.get(
            ctx.instance.runtime_properties['container_id'])
        container.stop()


@with_docker_client()
def delete_container(client, ctx):
    connected = ctx.instance.runtime_properties.get('connected', {})
    for target_name, connection_details in connected.items():
        # XXX client for that container
        network = client.networks.get(connection_details['net_id'])
        container = client.containers.get(connection_details['container_id'])
        network.disconnect(container)
        network.remove()

    if 'container_id' in ctx.instance.runtime_properties:
        container = client.containers.get(
            ctx.instance.runtime_properties['container_id'])
        container.remove()


@with_docker_client()
def create_network(client, ctx):
    props = ctx.node.properties
    network_name = ctx.node.properties['name'] or ctx.node.name
    external = ctx.node.properties['external']

    network = None
    try:
        network = client.networks.get(network_name)
    except docker.errors.NotFound:
        if external:
            raise

    if not external:
        if network:
            raise RuntimeError('Network {0} already exists'
                               .format(network_name))
        network = client.networks.create(
            name=network_name,
            driver=props['driver'],
            options=props['options']
        )

    ctx.logger.info('Created network: {0}'.format(network.name))
    ctx.instance.runtime_properties['network_id'] = network.id
    ctx.instance.runtime_properties['network_name'] = network_name


@with_docker_client()
def delete_network(client, ctx):
    if 'network_id' in ctx.instance.runtime_properties:
        if ctx.node.properties['external']:
            return
        network = client.networks.get(
            ctx.instance.runtime_properties['network_id'])
        network.remove()


@with_docker_client()
def create_volume(client, ctx):
    volume_name = ctx.node.properties['name'] or ctx.node.name
    mountpoint = ctx.node.properties.get('source')
    if not mountpoint:
        volume = client.volumes.create(
            name=volume_name,
            driver=ctx.node.properties['driver'],
            driver_opts=ctx.node.properties['driver_opts'],
        )
        ctx.logger.info('Created volume {0}'.format(volume.name))
        ctx.instance.runtime_properties['volume_created'] = True
        ctx.instance.runtime_properties['volume_id'] = volume.id
        mountpoint = volume.id
    else:
        ctx.instance.runtime_properties['volume_created'] = False
    ctx.instance.runtime_properties['volume_name'] = volume_name
    ctx.instance.runtime_properties['volume_mountpoint'] = mountpoint


@with_docker_client()
def delete_volume(client, ctx):
    if not ctx.instance.runtime_properties.get('volume_created'):
        return
    volume_name = ctx.instance.runtime_properties['volume_name']
    volume = client.volumes.get(ctx.instance.runtime_properties['volume_id'])
    volume.remove(force=True)
    ctx.logger.info('Removed volume {0}'.format(volume_name))


def copy_to_volume(client, volume_mountpoint, source, target=None):
    """Copy the source file or dir to the volume, under target path.

    This starts a container to copy the data - there's no clean way to
    edit data in a volume from outside a container. (we would need access
    to /var/lib/docker/volumes on the host running docker, so that might
    require ssh or similar).
    """
    if target is None:
        target = '/mnt/target'
    else:
        target = os.path.join('/mnt/target', target)

    volumes_config = {
        volume_mountpoint: {'bind': '/mnt/target'},
        source: {'bind': '/mnt/source'}
    }

    if os.path.isdir(source):
        cmd = ['bash', '-c', 'cp -r /mnt/source/* {0}'.format(target)]
    else:
        cmd = ['cp', '/mnt/source', target]

    try:
        client.images.get('ubuntu:latest')
    except docker.errors.ImageNotFound:
        client.images.pull('ubuntu', tag='latest')

    container = client.containers.create(
        image='ubuntu:latest',
        name='mgmtworker_config_writer',
        volumes=volumes_config,
        command=cmd
    )
    try:
        container.start()
        while True:
            time.sleep(0.1)
            container.reload()
            if container.status == 'exited':
                break
    finally:
        container.remove()
