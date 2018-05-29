
import os
import subprocess
import tempfile
import zipfile

from cloudify import ctx
from cloudify.exceptions import (
    NonRecoverableError,
    OperationRetry)


def unzip_archive(archive_path):
    """ Unzip a zip archive. """

    directory_to_extract_to = tempfile.mkdtemp()
    try:
        zip_ref = zipfile.ZipFile(archive_path, 'r')
    except zipfile.BadZipfile:
        raise NonRecoverableError(
            'File {0} is not a zip archive.'.format(
                archive_path))
    zip_ref.extractall(directory_to_extract_to)
    zip_ref.close()

    unzipped_work_directory = \
        os.path.join(
            directory_to_extract_to, zip_ref.namelist()[0])

    if not os.path.isdir(unzipped_work_directory):
        NonRecoverableError(
            'Directory {0} does not exist.'.format(
                unzipped_work_directory))

    return unzipped_work_directory


def get_package_dir(resource_path):
    """ Download unzip and return the path. """

    package_zip = ctx.download_resource(resource_path)
    package_dir = unzip_archive(package_zip)
    return package_dir


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

    if 'resource_path' not in resource_config:
        raise NonRecoverableError(
            "'resource_path' not in resource_config.")

    cwd = get_package_dir(resource_config['resource_path'])
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
