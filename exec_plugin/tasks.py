
import os
import subprocess
import tempfile
import zipfile

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError


def unzip_archive(archive_path):
    """ Unzip a zip archive. """

    directory_to_extract_to = tempfile.mkdtemp()
    zip_ref = zipfile.ZipFile(archive_path, 'r')
    zip_ref.extractall(directory_to_extract_to)
    zip_ref.close()

    unzipped_work_directory = \
        os.path.join(
            directory_to_extract_to, zip_ref.namelist()[0])

    if not os.path.isdir(unzipped_work_directory):
        raise

    return unzipped_work_directory


def get_package_dir(resource_path):
    """ Download unzip and return the path. """

    package_zip = ctx.download_resource(resource_path)
    package_dir = unzip_archive(package_zip)
    return package_dir


def execute(resource_config, file_to_source='exec',
            subprocess_args_overrides=None, timeout=60,
            ignore_failure=False, retry_on_failure=False, **_):

    """ Execute some file in an extracted archive. """

    if 'resource_path' not in resource_config:
        raise

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

    if isinstance(subprocess_args_overrides, dict):
        if 'env' in subprocess_args_overrides:
            _env_overrides = subprocess_args_overrides.pop('env')
            _env = os.environ.copy()
            if 'PATH' in _env_overrides:
                _env_path = _env_overrides.pop('PATH')
                _env["PATH"] = _env["PATH"] + _env_path
            subprocess_args_overrides['env'] = _env
        subprocess_args.update(subprocess_args_overrides)

    ctx.logger.debug('Args: {0}'.format(subprocess_args))

    process = subprocess.Popen(**subprocess_args)

    out, err = process.communicate()

    ctx.logger.debug('Out: {0}'.format(out))
    ctx.logger.debug('Err: {0}'.format(err))

    if process.returncode and retry_on_failure:
        raise OperationRetry('Retrying: {0}'.format(err))
    elif process.returncode and ignore_failure:
        raise NonRecoverableError('Failed: {0}'.format(err))
