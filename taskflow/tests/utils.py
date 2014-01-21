# -*- coding: utf-8 -*-

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import contextlib

import six

from taskflow import exceptions
from taskflow.persistence.backends import impl_memory
from taskflow import retry
from taskflow import task
from taskflow.utils import misc

ARGS_KEY = '__args__'
KWARGS_KEY = '__kwargs__'
ORDER_KEY = '__order__'


@contextlib.contextmanager
def wrap_all_failures():
    """Convert any exceptions to WrappedFailure.

    When you expect several failures, it may be convenient
    to wrap any exception with WrappedFailure in order to
    unify error handling.
    """
    try:
        yield
    except Exception:
        raise exceptions.WrappedFailure([misc.Failure()])


def make_reverting_task(token, blowup=False):

    def do_revert(context, *args, **kwargs):
        context[token] = 'reverted'

    if blowup:

        def blow_up(context, *args, **kwargs):
            raise RuntimeError("I blew up")

        return task.FunctorTask(blow_up, name='blowup_%s' % token)
    else:

        def do_apply(context, *args, **kwargs):
            context[token] = 'passed'

        return task.FunctorTask(do_apply, revert=do_revert,
                                name='do_apply_%s' % token)


class DummyTask(task.Task):

    def execute(self, context, *args, **kwargs):
        pass


class FakeTask(object):

    def execute(self, **kwargs):
        pass


if six.PY3:
    RUNTIME_ERROR_CLASSES = ['RuntimeError', 'Exception',
                             'BaseException', 'object']
else:
    RUNTIME_ERROR_CLASSES = ['RuntimeError', 'StandardError', 'Exception',
                             'BaseException', 'object']


class ProvidesRequiresTask(task.Task):
    def __init__(self, name, provides, requires, return_tuple=True):
        super(ProvidesRequiresTask, self).__init__(name=name,
                                                   provides=provides,
                                                   requires=requires)
        self.return_tuple = isinstance(provides, (tuple, list))

    def execute(self, *args, **kwargs):
        if self.return_tuple:
            return tuple(range(len(self.provides)))
        else:
            return dict((k, k) for k in self.provides)


class SaveOrderTask(task.Task):

    def __init__(self, name=None, *args, **kwargs):
        super(SaveOrderTask, self).__init__(name=name, *args, **kwargs)
        self.values = EngineTestBase.values

    def execute(self, **kwargs):
        self.update_progress(0.0)
        self.values.append(self.name)
        self.update_progress(1.0)
        return 5

    def revert(self, **kwargs):
        self.update_progress(0)
        self.values.append(self.name + ' reverted(%s)'
                           % kwargs.get('result'))
        self.update_progress(1.0)


class FailingTask(SaveOrderTask):
    def execute(self, **kwargs):
        self.update_progress(0)
        self.update_progress(0.99)
        raise RuntimeError('Woot!')


class TaskWithFailure(task.Task):

    def execute(self, **kwargs):
        raise RuntimeError('Woot!')


class ProgressingTask(task.Task):

    def execute(self, *args, **kwargs):
        self.update_progress(0.0)
        self.update_progress(1.0)
        return 5


class NastyTask(task.Task):

    def execute(self, **kwargs):
        pass

    def revert(self, **kwargs):
        raise RuntimeError('Gotcha!')


class NastyFailingTask(NastyTask):
    def execute(self, **kwargs):
        raise RuntimeError('Woot!')


class TaskNoRequiresNoReturns(task.Task):

    def execute(self, **kwargs):
        pass

    def revert(self, **kwargs):
        pass


class TaskOneArg(task.Task):

    def execute(self, x, **kwargs):
        pass

    def revert(self, x, **kwargs):
        pass


class TaskMultiArg(task.Task):

    def execute(self, x, y, z, **kwargs):
        pass

    def revert(self, x, y, z, **kwargs):
        pass


class TaskOneReturn(task.Task):

    def execute(self, **kwargs):
        return 1

    def revert(self, **kwargs):
        pass


class TaskMultiReturn(task.Task):

    def execute(self, **kwargs):
        return 1, 3, 5

    def revert(self, **kwargs):
        pass


class TaskOneArgOneReturn(task.Task):

    def execute(self, x, **kwargs):
        return 1

    def revert(self, x, **kwargs):
        pass


class TaskMultiArgOneReturn(task.Task):

    def execute(self, x, y, z, **kwargs):
        return x + y + z

    def revert(self, x, y, z, **kwargs):
        pass


class TaskMultiArgMultiReturn(task.Task):

    def execute(self, x, y, z, **kwargs):
        return 1, 3, 5

    def revert(self, x, y, z, **kwargs):
        pass


class TaskMultiDictk(task.Task):

    def execute(self):
        output = {}
        for i, k in enumerate(sorted(self.provides)):
            output[k] = i
        return output


class NeverRunningTask(task.Task):
    def execute(self, **kwargs):
        assert False, 'This method should not be called'

    def revert(self, **kwargs):
        assert False, 'This method should not be called'


class EngineTestBase(object):
    values = None

    def setUp(self):
        super(EngineTestBase, self).setUp()
        EngineTestBase.values = []
        self.backend = impl_memory.MemoryBackend(conf={})

    def tearDown(self):
        EngineTestBase.values = None
        with contextlib.closing(self.backend) as be:
            with contextlib.closing(be.get_connection()) as conn:
                conn.clear_all()
        super(EngineTestBase, self).tearDown()

    def _make_engine(self, flow, flow_detail=None):
        raise NotImplementedError()


class FailureMatcher(object):
    """Needed for failure objects comparison."""

    def __init__(self, failure):
        self._failure = failure

    def __repr__(self):
        return str(self._failure)

    def __eq__(self, other):
        return self._failure.matches(other)


class OneReturnRetry(retry.AlwaysRevert):

    def execute(self, **kwargs):
        return 1

    def revert(self, **kwargs):
        pass
