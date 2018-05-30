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

See below for blueprint installation instructions.


## Ansible Example

This example shows another use case: executing an Ansible workflow.

The blueprint uses the following files:

1. `exec`, which contains the core instructions.
1. `helloworld.yaml`, which is an Ansible Playbook.
1. `hosts.tmp`, which is the Ansible Inventory file.

The blueprint itself includes the files:

```yaml
  application:
    type: cloudify.nodes.Execution
    properties:
      resource_config:
        resource_list:
        - resources/ansible/exec
        - resources/ansible/helloworld.yml
        - resources/ansible/hosts.tmp
    relationships:
    - type: cloudify.relationships.contained_in
      target: host
```

You need your Cloudify Manager, with a secret for `agent_key_private` IP of a Ubuntu 14.04 VM to run this example. Use the instructions in the next step.


### Install the blueprint:

```bash
$ cfy blueprints upload examples/blueprint.yaml -b experiment-no-01
$ cfy deployments create --skip-plugins-validation -i host_ip=192.168.120.11 -b experiment-no-01
$ cfy executions start install -vv -d experiment-no-01
$ cfy executions start uninstall -vv -d experiment-no-01
```

__If you have a Kubernetes Cluster with Helm and Tiller running, you can install ONAP using the Helm files in `resources/helm`.__