import json
import subprocess


def create_machine(ctx, engine_opts=None):
    name = ctx.node.properties.get('name') or ctx.node.name

    if not ctx.node.properties.get('external'):
        driver = ctx.node.properties['driver']
        cmd = ['docker-machine', 'create', '-d', driver]
        if engine_opts is not None:
            for k, v in engine_opts.items():
                cmd.extend([
                    '--engine-opt',
                    '{0}={1}'.format(k, v)
                ])
        cmd.append(name)
        ctx.logger.info('Creating docker machine: {0}'.format(cmd))
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            ctx.logger.info('err {0}'.format(e))

    tls_enabled = ctx.node.properties.get('tls')
    tls_settings = {}
    if tls_enabled:
        tls_settings = ctx.node.properties['tls_settings']

    url = subprocess.check_output(['docker-machine', 'url', name]).strip()
    details = subprocess.check_output(['docker-machine', 'inspect', name])
    details = json.loads(details)

    ctx.instance.runtime_properties['name'] = name
    ctx.instance.runtime_properties['url'] = url
    ctx.instance.runtime_properties['connection_kwargs'] = {
        'base_url': url,
        'tls_enabled': tls_enabled,
        'tls_settings': tls_settings,
    }
    ctx.instance.runtime_properties['ip'] = details['Driver']['IPAddress']


def delete_machine(ctx):
    if not ctx.node.properties.get('external') \
            and not ctx.node.properties.get('keep'):
        name = ctx.instance.runtime_properties['name']
        subprocess.check_call(['docker-machine', 'rm', '-y', name])
