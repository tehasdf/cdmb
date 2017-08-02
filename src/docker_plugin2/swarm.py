from docker_plugin2.tasks import with_docker_client, find_relationship


MANAGER_RELATIONSHIP_TYPE = 'docker2.connected_to_swarm_manager'


@with_docker_client()
def start_swarm(client, ctx):
    spec = client.create_swarm_spec(
        snapshot_interval=5000, log_entries_for_slow_followers=1200
    )
    port = ctx.node.properties['swarm_port']
    start = ctx.node.properties['swarm_init']
    if start:
        client.init_swarm(
            advertise_addr='eth0',
            listen_addr='0.0.0.0:{0}'.format(port),
            force_new_cluster=False,
            swarm_spec=spec
        )
    else:
        manager_links = find_relationship(ctx.instance.relationships,
                                          MANAGER_RELATIONSHIP_TYPE)
        if len(manager_links) != 1:
            ctx.abort_operation('{0} should have 1 manager link but has {1}'
                                .format(ctx.instance.id, len(manager_links)))
        manager_instance = manager_links[0].target.instance
        manager_swarm_info = manager_instance.runtime_properties['swarm']
        worker_token = manager_swarm_info['JoinTokens']['Worker']
        manager_addr = '{0}:2376'.format(manager_instance.host_ip)
        joined = client.join_swarm(
            remote_addrs=[manager_addr],
            join_token=worker_token,
            listen_addr='0.0.0.0:{0}'.format(port),
            advertise_addr='eth0:5000'
        )
        print joined

    swarm_info = client.inspect_swarm()
    ctx.instance.runtime_properties['swarm'] = swarm_info
