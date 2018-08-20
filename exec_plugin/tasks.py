
import os
import subprocess
import tempfile
import errno
import zipfile
import copy

from cloudify import ctx
from cloudify.exceptions import (
    NonRecoverableError,
    OperationRetry)


def verify_os_file_path(os_file_path):
    if not os.path.exists(os_file_path):
        return
    return os_file_path


def get_directory_by_property_name(property_name,
                                   creation_action=None,
                                   creation_action_args=None,
                                   creation_action_kwargs=None):

    directory = \
        str(ctx.instance.runtime_properties.get(
            property_name))

    if not verify_os_file_path(directory):
        ctx.logger.warn(
            'No runtime property "{0}" set. '
            'Creating new directory.'.format(property_name))
        if creation_action_args and creation_action_kwargs:
            directory = creation_action(
                *creation_action_args, **creation_action_kwargs)
        elif creation_action_args:
            directory = creation_action(*creation_action_args)
        elif creation_action_kwargs:
            directory = creation_action(**creation_action_kwargs)
        else:
            directory = creation_action()
        ctx.instance.runtime_properties[property_name] = \
            directory

    return verify_os_file_path(directory)


def get_current_working_directory():
    return get_directory_by_property_name(
        'current_working_directory',
        tempfile.mkdtemp)


def get_blueprint_directory():
    return get_directory_by_property_name(
        'blueprint_directory',
        lambda: '/opt/manager/resources/blueprints/{0}/{1}'.format(
            ctx.tenant_name, ctx.blueprint.id))


def extract_archive_from_path(archive_path,
                              target_directory,
                              intermediate_actions=None):
    return_value = None
    with zipfile.ZipFile(archive_path) as archive:
        if intermediate_actions:
            return_value = intermediate_actions()
        archive.extractall(target_directory)
        return return_value


def get_resource_relative_path(resource, relative_dir):
    """
    :param resource: Entry of the list returned by os.walk()
        containing absolute path of a resource
    :param relative_dir: Directory, which the resource is relative to
    :return: String object containing relative path of the resource
    """
    return resource[0][len(relative_dir) + 1:]


def get_package_dir_from_dir_and_list(resource_dir,
                                      resource_list,
                                      template_variables={}):
    # Case, when user defines a directory with files, which need to be
    # downloaded, but doesn't want to render all of them - only these
    # defined in resource_list.

    ctx.logger.debug('resource_dir and resource_list params are not empty.')

    # Deal with ZIP files
    filename, extension = os.path.splitext(resource_dir)
    if extension == '.zip':
        archive_path = os.path.join(get_blueprint_directory(), resource_dir)
        target_directory = os.path.join(get_blueprint_directory(), filename)
        resource_dir = filename
        extract_archive_from_path(archive_path, target_directory)

    # Deal with ZIP files in resource_list
    for template_path in copy.copy(resource_list):

        filename, extension = os.path.splitext(template_path)

        if extension == '.zip':
            resource_list.remove(template_path)
            archive_path = os.path.join(
                get_blueprint_directory(), resource_dir, template_path)
            target_directory = os.path.join(
                get_blueprint_directory(), resource_dir, filename)
            extract_archive_from_path(archive_path, target_directory)

            for extracted_template in os.walk(target_directory):
                extracted_template_path = get_resource_relative_path(
                    extracted_template,
                    os.path.join(get_blueprint_directory(), resource_dir))
                if extracted_template[2]:
                    for filename in extracted_template[2]:
                        resource_list.append(
                            os.path.join(extracted_template_path, filename))
                elif not extracted_template[1] and not extracted_template[2]:
                    resource_list.append(extracted_template_path)

    merged_list = []

    # This loop goes through a directory defined in resource_dir parameter
    # and prepares a list of paths inside it.
    for resource_path in os.walk(os.path.join(
            get_blueprint_directory(), resource_dir)):
        trimmed_resource_path = get_resource_relative_path(
            resource_path, os.path.join(get_blueprint_directory()))
        if resource_path[2]:
            for filename in resource_path[2]:
                merged_list.append(
                    os.path.join(trimmed_resource_path, filename))
        elif not resource_path[1] and not resource_path[2]:
            merged_list.append(trimmed_resource_path)

    # This loop goes through a templates list defined in resource_list
    # parameter. For each template it renders it (resolves all of variables
    # defined in template_variables parameter) and downloads it to working
    # directory. Finally, it removes a path to this file from the merged_list,
    # because it should be ommitted at the next step, which is copying the rest
    # of the files, which are not templates.
    for template_path in resource_list:
        template_dirname = os.path.join(
            resource_dir, os.path.dirname(template_path))
        download_from_file = os.path.join(resource_dir, template_path)
        download_to_directory = os.path.join(
            get_current_working_directory(), template_dirname)
        download_to_file = os.path.join(
            get_current_working_directory(), download_from_file)

        try:
            os.makedirs(download_to_directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        ctx.download_resource_and_render(
            download_from_file,
            download_to_file,
            template_variables.copy())

        if os.path.splitext(download_to_file)[1] == '.py':
            os.chmod(download_to_file, 0755)

        if download_from_file in merged_list:
            merged_list.remove(download_from_file)

    # This loop goes through the merged_list and downloads the rest of
    # files to our working directory.
    for resource_path in merged_list:
        resource_dirname = os.path.dirname(resource_path)
        download_to_directory = os.path.join(
            get_current_working_directory(), resource_dirname)
        download_to_file = os.path.join(
            get_current_working_directory(), resource_path)

        try:
            os.makedirs(download_to_directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        try:
            ctx.download_resource(
                resource_path,
                download_to_file)
        except OSError as e:
            if e.errno != errno.EISDIR:
                raise

        if os.path.splitext(download_to_file)[1] == '.py':
            os.chmod(download_to_file, 0755)

    return get_current_working_directory()


def get_package_dir_from_dir(resource_dir, template_variables={}):
    # Case, when user defines path to a directory, where files, which need to
    # be downloaded and rendered, reside.

    ctx.logger.debug('only resource_dir is not empty.')

    # Deal with ZIP files
    filename, extension = os.path.splitext(resource_dir)
    if extension == '.zip':
        archive_path = os.path.join(get_blueprint_directory(), resource_dir)
        target_directory = os.path.join(get_blueprint_directory(), filename)
        resource_dir = filename
        extract_archive_from_path(archive_path, target_directory)

    merged_list = []

    # This loop goes through a directory defined in resource_dir parameter
    # and prepares a list of paths inside it.
    for resource_path in os.walk(
            os.path.join(get_blueprint_directory(), resource_dir)):
        trimmed_resource_path = get_resource_relative_path(
            resource_path, os.path.join(get_blueprint_directory()))

        if resource_path[2]:
            for filename in resource_path[2]:
                merged_list.append(
                    os.path.join(trimmed_resource_path, filename))
        elif not resource_path[1] and not resource_path[2]:
            merged_list.append(trimmed_resource_path)

    # This loop goes through the merged_list and downloads the rest of
    # files to our working directory.
    for template_path in merged_list:
        template_dirname = os.path.dirname(template_path)
        download_from_file = template_path
        download_to_directory = os.path.join(
            get_current_working_directory(), template_dirname)
        download_to_file = os.path.join(
            get_current_working_directory(), download_from_file)

        try:
            os.makedirs(download_to_directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        ctx.download_resource_and_render(
            download_from_file,
            download_to_file,
            template_variables.copy())

        if os.path.splitext(download_to_file)[1] == '.py':
            os.chmod(download_to_file, 0755)

    return get_current_working_directory()


def get_package_dir_from_list(resource_list, template_variables={}):
    # Case, when user defines a list of files in resource_list,
    # which need to be downloaded and rendered.

    ctx.logger.debug('only resource_list is not empty.')

    # Deal with ZIP files in resource_list
    for template_path in copy.copy(resource_list):

        filename, extension = os.path.splitext(template_path)

        if extension == '.zip':

            resource_list.remove(template_path)

            archive_path = os.path.join(
                get_blueprint_directory(), template_path)
            target_directory = os.path.join(
                get_blueprint_directory(), filename)
            extract_archive_from_path(archive_path, target_directory)

            for extracted_template in os.walk(target_directory):
                extracted_template_path = get_resource_relative_path(
                    extracted_template, get_blueprint_directory())
                if extracted_template[2]:
                    for filename in extracted_template[2]:
                        resource_list.append(
                            os.path.join(extracted_template_path, filename))
                elif not extracted_template[1] and not extracted_template[2]:
                    resource_list.append(extracted_template_path)

    for template_path in resource_list:
        resource_name = os.path.basename(template_path)
        download_to = os.path.join(
            get_current_working_directory(), resource_name)
        ctx.download_resource_and_render(
            template_path,
            download_to,
            template_variables.copy())

    return get_current_working_directory()


def get_package_dir(resource_dir='', resource_list=[], template_variables={}):
    """ Download resources and return the path. """

    if resource_dir and resource_list:
        return get_package_dir_from_dir_and_list(
            resource_dir=resource_dir,
            resource_list=resource_list,
            template_variables=template_variables)
    elif resource_dir and not resource_list:
        return get_package_dir_from_dir(
            resource_dir=resource_dir,
            template_variables=template_variables)
    elif not resource_dir and resource_list:
        return get_package_dir_from_list(
            resource_list=resource_list,
            template_variables=template_variables)
    else:
        raise NonRecoverableError("At least one of the two properties, \
            resource_dir or resource_list, has to be defined.")


def handle_overrides(overrides, current):
    if not isinstance(overrides, dict):
        INVALID_OVERRIDES_ERROR = \
            'Invalid overrides {0}: not a dict.'
        ctx.logger.debug(
            INVALID_OVERRIDES_ERROR.format(overrides))
        return
    if overrides.pop('PERSIST_CFY_AGENT_ENV_BOOL', True):
        env = os.environ.copy()
        _overrides_env = overrides.pop('env', {})
        _overrides_path = _overrides_env.pop('PATH', '')
        if _overrides_path:
            if not _overrides_path.startswith(':'):
                _overrides_path = ':' + _overrides_path
            _overrides_env['PATH'] = env['PATH'] + _overrides_path
        env.update(_overrides_env)
        overrides['env'] = env
    current.update(overrides)


def execute(resource_config,
            file_to_source='exec',
            subprocess_args_overrides=None,
            ignore_failure=False,
            retry_on_failure=False, **_):

    """ Execute some file in an extracted archive. """

    resource_config = \
        resource_config or ctx.node.properties['resource_config']

    resource_dir = resource_config.get('resource_dir', '')
    resource_list = resource_config.get('resource_list', [])
    template_variables = resource_config.get('template_variables', {})

    if not isinstance(resource_dir, basestring):
        raise NonRecoverableError("'resource_dir' must be a string.")

    if not isinstance(resource_list, list):
        raise NonRecoverableError("'resource_list' must be a list.")

    if not isinstance(template_variables, dict):
        raise NonRecoverableError("'template_variables' must be a dictionary.")

    if resource_dir:
        tmp_dir = get_package_dir(
            resource_dir, resource_list, template_variables)
        # in case of resource_dir is zip
        cwd = os.path.join(
            tmp_dir, os.path.splitext(resource_dir)[0])
    else:
        cwd = get_package_dir(resource_dir, resource_list, template_variables)
    command = ['bash', '-c', 'source {0}'.format(file_to_source)]

    subprocess_args = \
        {
            'args': command,
            'stdin': subprocess.PIPE,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'cwd': cwd
        }

    handle_overrides(subprocess_args_overrides, subprocess_args)

    ctx.logger.debug('Args: {0}'.format(subprocess_args))

    process = subprocess.Popen(**subprocess_args)

    out, err = process.communicate()
    ctx.logger.debug('Out: {0}'.format(out))
    ctx.logger.debug('Err: {0}'.format(err))

    if process.returncode and retry_on_failure:
        raise OperationRetry('Retrying: {0}'.format(err))

    elif process.returncode and not ignore_failure:
        raise NonRecoverableError('Failed: {0}'.format(err))
