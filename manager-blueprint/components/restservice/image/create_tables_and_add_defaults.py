#!/usr/bin/env python
#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from flask_migrate import upgrade

from manager_rest.config import instance as config
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage.storage_utils import \
    create_default_user_tenant_and_roles


def _init_db_tables(config):
    print 'Setting up a Flask app'
    app = setup_flask_app(
        manager_ip=config.postgresql_host,
        hash_salt=config.security_hash_salt,
        secret_key=config.security_secret_key
    )
    with app.app_context():
        print 'Creating tables in the DB'
        upgrade(directory='/opt/cloudify-manager/'
                          'resources/rest-service/cloudify/migrations/')


def _add_default_user_and_tenant(config, amqp_manager):
    print 'Creating bootstrap admin, default tenant and security roles'
    create_default_user_tenant_and_roles(
        admin_username='admin',
        admin_password='admin',
        amqp_manager=amqp_manager
    )


def _get_amqp_manager(config):
    return AMQPManager(
        host=config.amqp_host,
        username=config.amqp_username,
        password=config.amqp_password
    )


if __name__ == '__main__':
    # We're expecting to receive as an argument the path to the config file
    config.load_configuration()
    _init_db_tables(config)
    amqp_manager = _get_amqp_manager(config)
    _add_default_user_and_tenant(config, amqp_manager)
    print 'Finished creating bootstrap admin and default tenant'
