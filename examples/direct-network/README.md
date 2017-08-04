# Two containers connected directly

This example shows the `container_connected_to_container` relationship which
creates a network implicitly and connects both containers to it. They are then
addressable by their node name (can be overridden using the `network_aliases`
property).

This is a simple way to connect two containers, for more complex networking
setups see the [explicit networ](../explicit-network) example.

After running the blueprint, see the output of `docker logs host_b` to see
the ping command output.
