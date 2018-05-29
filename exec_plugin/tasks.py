
import os
import subprocess
import tempfile

from cloudify import ctx
from cloudify.exceptions import (
    NonRecoverableError,
    OperationRetry)


def get_package_dir(resource_list, template_variables):
    """ Download resources and return the path. """

    work_dir = tempfile.mkdtemp()
    for resource_path in resource_list:
        resource_name = os.path.basename(resource_path)
        download_to = os.path.join(work_dir, resource_name)
        ctx.download_resource_and_render(
            resource_path,
            download_to,
            template_variables)
    return work_dir


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

    resource_list = resource_config.get('resource_list', [])
    template_variables = resource_config.get('template_variables', {})

    if not isinstance(resource_list, list) or not len(resource_list) > 0:
        raise NonRecoverableError("'resource_list' must be a list.")

    cwd = get_package_dir(resource_list, template_variables)
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
