# cloudify-execution-plugin

Execute code that is packaged in a zip file.

## Prerequisites

  * Cloudify Manager, 3.4.2+.

## Packaging Code:

1. Create a new empty folder.
1. Create a file in the folder called "exec". (You can override this, but why?)
1. All instructions should be written in the exec file in __bash__.
1. Zip up the folder.

## Include in a blueprint.

Create a node template in your blueprint such as this:

```yaml

  application:
    type: cloudify.nodes.Execution
    properties:
      resource_config:
        resource_path: resources/my_code.zip
    relationships:
    - type: cloudify.relationships.contained_in
      target: host

```

You should also have a compute node, such as:

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

## Examples

There are three examples. The simplest is for installing _Apache2_. Then graduate to _Ansible_. From there, if you have a _Kubernetes Cluster_ with _Tiller_, you can run the _Helm_ example.

For each zip the folder. Then install the `blueprint.yaml`, toggling the name of the archive and the host ip of an existing VM.

__Note: For the Helm, example, you must already have Kubernetes and Helm running.__
