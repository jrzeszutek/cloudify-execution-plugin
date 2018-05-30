# cloudify-execution-plugin

Execute code contained in a list of files.

The plugin creates a temporary directory. It will execute everything relative to the directory. By default it will look for a file named `exec` in the temporary directory and follow any instructions that you put there.


## Prerequisites

  * Cloudify Manager, 3.4.2+.
  * You need a minimal VM. Any node type derived from `cloudify.nodes.Compute` will do.


## Example:


### Writing your script:

Relative to your blueprint, create some folder with a file in it named `exec`.

```bash
#!/bin/bash

# content of resources/hello_world/exec

echo "hello world"
```

Next write a blueprint.


###  Writing the blueprint.

The Cloudify Agent on some VM will execute your code. Here is an example VM.

```yaml

  host:
    type: cloudify.nodes.Compute
    properties:
      ip: { get_input: host_ip }
      agent_config:
        install_method: remote
        port: 22
        user: { get_input: username }
        key: { get_secret: agent_key_private }

```

Create a execution node template in your blueprint such as this:

```yaml

  application:
    type: cloudify.nodes.Execution
    properties:
      resource_config:
        resource_list:
        - resources/hello_world/exec
    relationships:
    - type: cloudify.relationships.contained_in
      target: host

```


### Install the blueprint:

```bash
$ cfy blueprints upload examples/blueprint.yaml -b experiment-no-01
$ cfy deployments create --skip-plugins-validation -i host_ip=192.168.120.11 -b experiment-no-01
$ cfy executions start install -vv -d experiment-no-01
$ cfy executions start uninstall -vv -d experiment-no-01
```
