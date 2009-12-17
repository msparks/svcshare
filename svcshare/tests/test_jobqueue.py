import time
from nose.tools import *
from svcshare import jobqueue
from svcshare import exc


class Test_Job:
  def test_createJob(self):
    def foo():
      pass
    name = "foobar"
    func = foo
    args = [1, 2, 3]
    delay = 3
    periodic = True
    job = jobqueue.Job(name, func, args, delay, periodic)
    assert_equals(job.name(), name)
    assert_equals(job.func(), func)
    assert_equals(job.args(), args)
    assert_equals(job.delay(), delay)
    assert_equals(job.periodic(), periodic)


class Test_JobQueue:
  def foo(self):
    pass

  def bar(self):
    pass

  def setup(self):
    self.q = jobqueue.JobQueue()

  def test_addJob(self):
    self.q.jobNew("foo", self.foo, delay=0)
    assert_equals(self.q.hasNextJob(), True)
    assert_equals(self.q.nextJob().name(), "foo")

  @raises(exc.NameInUseException)
  def test_duplicateAdd(self):
    self.q.jobNew("foo", self.foo)
    self.q.jobNew("foo", self.foo)

  def test_delay(self):
    epoch = time.time()
    self.q.jobNew("foo", self.foo, delay=3)
    self.q.jobNew("bar", self.bar, delay=8)

    assert_equals(self.q.nextJob(), None)
    self.q.epochIs(epoch + 3.1)
    assert_equals(self.q.nextJob().name(), "foo")
    self.q.epochIs(epoch + 8.1)
    assert_equals(self.q.nextJob().name(), "bar")
    assert_equals(self.q.hasNextJob(), False)

  def test_removeJob(self):
    self.q.jobNew("foo", self.foo)
    self.q.jobNew("bar", self.bar)
    assert_equals(self.q.jobDel("foo").name(), "foo")
    assert_equals(self.q.jobDel("bar").name(), "bar")
    assert_equals(self.q.hasNextJob(), False)

  @raises(exc.NameNotFoundException)
  def test_duplicateRemove(self):
    self.q.jobNew("foo", self.foo)
    self.q.jobDel("foo")
    self.q.jobDel("foo")
