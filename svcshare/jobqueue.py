import time


class Job(object):
  """Class representing a job in a JobQueue."""
  def __init__(self, func, args=None, delay=0, periodic=False, name=None):
    if args is None:
      args = []
    self.func = func
    self.args = args
    self.epoch = time.time() + delay
    self.periodic = periodic
    self.delay = delay
    self.name = name

  def __str__(self):
    return "<Job '%s': %s>" % (self.name, self.func)


class JobQueue(object):
  def __init__(self):
    self._queue = []

  def add_job(self, func, args=None, delay=0, periodic=False, name=None):
    """Add a new job to the job queue.

    Args:
      func: function reference to run
      args: list of arguments to pass to the function
      delay: deadline from now in seconds
      periodic: automatically re-enqueue this job when it runs
      name: name to assign to this job
    """
    new_job = Job(func, delay=delay, args=args, periodic=periodic, name=name)
    for idx, job in enumerate(self._queue):
      if job.epoch > new_job.epoch:
        self._queue.insert(idx, new_job)
        break
    else:
      self._queue.append(new_job)

  def has_next_job(self):
    """Checks to see if a job is ready to run.

    Returns:
      True or False
    """
    if not self._queue or self._queue[0].epoch > time.time():
      return False
    else:
      return True

  def next_job(self):
    """Gets next job in the queue if one is available.

    Returns:
      Job object of next job in the queue, or None if none are due or available.
    """
    if not self.has_next_job():
      return None
    job = self._queue.pop(0)
    if job.periodic:
      self.add_job(job.func, args=job.args, delay=job.delay,
                   periodic=job.periodic)
    return job

  def remove_job(self, name):
    """Remove a job specified by name.

    Args:
      name: name of job to remove. A job must have a name to be removed.

    Returns:
      True if successful, False if not
    """
    removed = False
    for idx, job in enumerate(self._queue):
      if job.name == name:
        del self._queue[idx]
        removed = True
    return removed


if __name__ == "__main__":
  def foo():
    pass

  def bar():
    pass

  q = JobQueue()
  q.add_job(foo, delay=3)
  q.add_job(bar, delay=8)

  assert(q.next_job() is None)
  time.sleep(3.1)
  assert(q.next_job().func == foo)
  time.sleep(5)
  assert(q.next_job().func == bar)
  assert(q.has_next_job() == False)

  q.add_job(foo, name="foo")
  q.add_job(bar, name="bar")
  assert(q.remove_job("foo") == True)
  assert(q.remove_job("foo") == False)
  assert(q.remove_job("bar") == True)
  assert(q.has_next_job() == False)
  assert(q.remove_job("bar") == False)

  q.add_job(foo, name="foo")
  q.add_job(bar, name="bar")
  q.add_job(foo, name="foo")
  q.remove_job("foo")
  assert(q.next_job().name == "bar")
  assert(q.has_next_job() == False)

  print "All tests passed."
