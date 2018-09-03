# cloudify-execution-plugin

Execute arbitrary code. Specify a list of resources, such as scripts, binaries, dependencies in a single node template. The root script file `exec` will contain all of your instructions.

**Example Node Template**

```yaml

  application:
    type: cloudify.nodes.Execution
    properties:
      resource_config:
        resource_list:
        - resources/exec
        - resources/my_binary
        - resources/data.json
    relationships:
    - type: cloudify.relationships.contained_in
      target: host

```

**Example Exec Script**

```bash
#!/bin/bash

# content of resources/exec
source ./my_file
./my_binary -arg my_file <$(cat ./data.json)

```

**What happens**

The plugin creates a temporary directory. What happens then, depends on defined properties.

  * 1st use case: both `resource_dir` and `resource_list` are defined

  Plugin renders all of the files defined in `resource_list` with the values \
  defined in `template_variables` (if empty, it just copies the files unchanged \
  to temporary working directory) and copies rendered files to temporary \
  directory. The rest of files inside `resource_dir` directory are copied \
  unchanged.

  If `resource_dir` is a zip file, its content is being extracted first. If \
  there are any zip files defined in `resource_list`, they are also being \
  extracted.

  * 2nd use case: `resource_dir` is defined and `resource_list` is not

  Plugin renders all of the files inside of a directory (or files extracted \
  from zip archive) \
  defined in `resource_dir` with the values defined in `template_variables`. \
  If `template_variables` is not empty, files extracted from `resource_dir` are \
  being rendered with them and copied to temporary directory. If `template_variables` \
  is empty, then files are just being copied (without rendering).

  * 3rd use case: `resource_dir` is not defined and `resource_list` is defined

  Plugin renders all of the files in `resource_list` (including these extracted \
  from zip files being a part of a `resource_list`) with the values defined in \
  `template_variables` and copies them to temporary directory. If \
  `template_variables` is empty, then files are just being copied (without \
  rendering).

Plugin will then execute the `exec` file relative to the temporary directory.

_Note: By default the plugin looks to execute a file named `exec` in the temporary directory. This may be overridden._

## Prerequisites

  * Cloudify Manager, 3.4.2+.
  * You need a minimal VM. Any node type derived from `cloudify.nodes.Compute` will do.


## Operations

There is only one task defined in the plugin `execute`. This function wraps a `subprocess.Popen` [constructor](https://docs.python.org/2/library/subprocess.html#subprocess.Popen).

  * `cloudify.interfaces.lifecycle.create`
    * `implementation: exec.exec_plugin.tasks.execute`

The `create` operation can be remapped to other lifecycle interface operations, such as `start` or `stop`, etc.

Other `subprocess.Popen` features can be via `inputs`, for example add environment variables:

```yaml
  application:
    type: cloudify.nodes.Execution
    properties:
      resource_config:
        resource_list:
        - resources/exec
        - resources/install.sh
        - resources/uninstall.sh
    relationships:
    - type: cloudify.relationships.contained_in
      target: host
    interfaces:
      cloudify.interfaces.lifecycle:
        create:
          implementation: exec.exec_plugin.tasks.execute
          inputs:
            resource_config: { get_property: [ SELF, resource_config ] }
            subprocess_args_overrides:
              env:
                JOB: 'install'
        delete:
          implementation: exec.exec_plugin.tasks.execute
          inputs:
            resource_config: { get_property: [ SELF, resource_config ] }
            subprocess_args_overrides:
              env:
                JOB: 'uninstall'
```

You can call different scripts from different lifecycle operations in the main `exec` file by adding conditional bash logic:

```bash
if [[ "$JOB" == "install" ]]
then
    chmod 755 install.sh
    ./install.sh
elif [[ "$JOB" == "uninstall" ]]
then
    chmod 755 uninstall.sh
    ./uninstall.sh
fi

```

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
