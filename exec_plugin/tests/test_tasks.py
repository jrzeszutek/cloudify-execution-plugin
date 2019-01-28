# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

# Built-in Imports
import os
import mock
import tempfile
import testtools

# Third Party Imports
from cloudify.state import current_ctx
from cloudify.mocks import MockCloudifyContext
from cloudify.exceptions import (
    NonRecoverableError,
    OperationRetry)

from .. import tasks


class TestTasks(testtools.TestCase):

    def tearDown(self):
        super(TestTasks, self).tearDown()
        if os.path.exists(os.path.join(os.curdir, 'exec')):
            os.remove(os.path.join(os.curdir, 'exec'))

    def setUp(self):
        super(TestTasks, self).setUp()

    def mock_ctx(self, test_name):

        test_node_id = test_name
        test_properties = {
            'resource_config': {
                'resource_list': [
                    'resources/folders/ansible/exec',
                    'helloworld.yml',
                    'hosts.tmp'
                ],
            },
        }

        return MockCloudifyContext(
            node_id=test_node_id,
            properties=test_properties)

    @mock.patch('os.environ.copy',
                return_value={'PATH': '/bin:/usr/sbin:/sbin'})
    def test_handle_overrides_persist(self, m_env):
        ctx = self.mock_ctx('test_handle_overrides_persist')
        assert ctx
        t_current = {
            'args': 'hello world',
            'env': {
                'PATH': '/bin:/usr/sbin:/sbin',
                'SCRIPT_NAME': 'script name'
            }
        }
        t_overrides = {
            'a': '_a',
            'b': '_b',
            'PERSIST_CFY_AGENT_ENV_BOOL': True,
            'env': {
                'PATH': '/other',
                'SCRIPT_NAME': 'script name'
            }
        }
        expected = {
            'a': '_a',
            'b': '_b',
            'args': 'hello world',
            'env': {
                'PATH': '/bin:/usr/sbin:/sbin:/other',
                'SCRIPT_NAME': 'script name'
            }
        }
        tasks.handle_overrides(t_overrides, t_current)
        self.assertEqual(t_current, expected)

    def test_handle_overrides_no_persist(self):
        ctx = self.mock_ctx('test_handle_overrides_no_persist')
        assert ctx
        t_current = {
            'args': 'hello world',
            'env': {
                'PATH': '/bin:/usr/sbin:/sbin',
                'SCRIPT_NAME': 'script name'
            }
        }
        t_overrides = {
            'a': '_a',
            'b': '_b',
            'PERSIST_CFY_AGENT_ENV_BOOL': False,
            'env': {
                'PATH': '/other/path',
                'SCRIPT_NAME': 'script name'
            }
        }
        expected = {
            'a': '_a',
            'b': '_b',
            'args': 'hello world',
            'env': {
                'PATH': '/other/path',
                'SCRIPT_NAME': 'script name'
            }
        }
        tasks.handle_overrides(t_overrides, t_current)
        self.assertEqual(t_current, expected)

    def test_execute_no_resource_config(self):
        ctx = self.mock_ctx('test_execute_no_resource_config')
        current_ctx.set(ctx=ctx)
        del ctx.node.properties['resource_config']['resource_list']
        self.assertRaises(
            NonRecoverableError,
            tasks.execute,
            resource_config=ctx.node.properties['resource_config'],
            ctx=ctx)

    def test_execute_non_binary(self):
        ctx = self.mock_ctx('test_execute_non_binary')
        _, filename = tempfile.mkstemp()
        with open(filename, 'w') as fout:
            fout.write('Test ')
        ctx.download_resource_and_render = mock.MagicMock()
        ctx.download_resource = mock.MagicMock()
        ctx.node.properties['resource_config']['resource_list'] = [filename]
        current_ctx.set(ctx=ctx)
        self.assertRaises(
            NonRecoverableError,
            tasks.execute,
            resource_config=ctx.node.properties['resource_config'],
            ctx=ctx)

    def test_execute_binary_package(self):
        ctx = self.mock_ctx('test_execute_binary_package')
        _, filename = tempfile.mkstemp()
        with open(filename, 'wb') as fout:
            fout.write('Test\0')
        ctx.download_resource_and_render = mock.MagicMock()
        ctx.download_resource = mock.MagicMock()
        ctx.node.properties['resource_config']['resource_list'] = [filename]
        current_ctx.set(ctx=ctx)
        self.assertRaises(
            NonRecoverableError,
            tasks.execute,
            resource_config=ctx.node.properties['resource_config'],
            ctx=ctx)
        os.remove(filename)

    @mock.patch('exec_plugin.tasks.get_package_dir', return_value=os.curdir)
    def test_execute_good(self, m_cwd):
        with open(os.path.join(m_cwd(), 'exec'), 'w') as f:
            f.write('echo "hello world"')
        ctx = self.mock_ctx('test_execute_good')
        current_ctx.set(ctx=ctx)
        tasks.execute(
            resource_config=ctx.node.properties['resource_config'],
            ctx=ctx)

    @mock.patch('exec_plugin.tasks.get_package_dir', return_value=os.curdir)
    def test_execute_bad_script(self, m_cwd):
        ctx = self.mock_ctx('test_execute_bad_script')
        current_ctx.set(ctx=ctx)
        process = mock.MagicMock()
        process.return_code = True
        process.communicate = mock.MagicMock(
            return_value=('Out', 'Err'))
        with mock.patch('subprocess.Popen', return_value=process):
            self.assertRaises(
                NonRecoverableError,
                tasks.execute,
                resource_config=ctx.node.properties['resource_config'],
                ctx=ctx)

    @mock.patch('exec_plugin.tasks.get_package_dir', return_value=os.curdir)
    def test_execute_bad_script_retry(self, m_cwd):
        ctx = self.mock_ctx('test_execute_bad_script_retry')
        current_ctx.set(ctx=ctx)
        process = mock.MagicMock()
        process.return_code = True
        process.communicate = mock.MagicMock(
            return_value=('Out', 'Err'))
        with mock.patch('subprocess.Popen', return_value=process):
            self.assertRaises(
                OperationRetry,
                tasks.execute,
                retry_on_failure=True,
                resource_config=ctx.node.properties['resource_config'],
                ctx=ctx)

    @mock.patch('exec_plugin.tasks.get_package_dir', return_value=os.curdir)
    def test_execute_bad_script_ignore(self, m_cwd):
        ctx = self.mock_ctx('test_execute_bad_script_ignore')
        current_ctx.set(ctx=ctx)
        process = mock.MagicMock()
        process.return_code = True
        process.communicate = mock.MagicMock(
            return_value=('Out', 'Err'))
        with mock.patch('subprocess.Popen', return_value=process):
            tasks.execute(
                ignore_failure=True,
                resource_config=ctx.node.properties['resource_config'],
                ctx=ctx)
