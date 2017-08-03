Cloudify docker plugin & manager blueprint
==========================================

This is a proof of concept of a new Cloudify docker plugin implementation.
For a complete example, see the manager blueprint.

Installing the plugin
---------------------

Simply install the plugin from the src/ subdirectory using pip.


Installing the manager blueprint
--------------------------------

The blueprint is inside the manager-blueprint subdirectory.
Use cfy local to install it, eg. like this:

.. code-block:: bash

    cfy init -b bp manager-blueprint/simple_blueprint.yaml --install-plugins
    cfy exec start -b bp install
    cfy deployment outputs -b bp # to see the allocated IP
    cfy profiles use 1.2.3.4 -u admin -p admin -t default_tenant # with that IP
