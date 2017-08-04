# Container built from a Dockerfile

This example uses a Dockerfile to build an image, from which a container is then created.

The container simply runs a command and exit, to verify that it worked correctly,
you can do the following:

```sh
cfy init -b bp bp.yaml
cfy exec start -b bp install
docker logs hw  # the "hw" container should have logged "Hello world"
```


### files.lst

The [image/](image) directory contains a `files.lst` file listing all the files
in it. This is due to a Cloudify limitation - it is only possible to download
files using `ctx.download_resource`, not directories - hence we download the
files one by one.
