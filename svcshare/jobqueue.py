import time
import exc


class Job(object):
  """Class representing a job in a JobQueue."""
  def __init__(self, name, func, args=None, delay=0, periodic=False):
    if args is None:
      args = []
    self._name = name
    self._func = func
    self._args = args
    self._epoch = time.time() + delay
    self._delay = delay
    self._periodic = periodic

  def __str__(self):
    return "<Job '%s': %s>" % (self.name(), self.func())

  def name(self):
    return self._name

  def func(self):
    return self._func

  def args(self):
    return self._args

  def delay(self):
    return self._delay

  def epoch(self):
    return self._epoch

  def periodic(self):
    return self._periodic


class JobQueue(object):
  def __init__(self):
    self._queue = []
    self._epoch = 0

  def epoch(self):
    """Access the internal job queue epoch.

    This value is the epoch used to determine when to pop jobs from the queue.
    The internal epoch typically follows time.time(). If epochIs() is used to
    change the time, all subsequent requests to epoch(), including those used
    internally in the job queue, will use the time set by epochIs(). Thus, time
    can be manually advanced using this method.

    Args:
      none

    Returns:
      internal epoch value
    """
    if self._epoch == 0:
      return time.time()
    else:
      return self._epoch

  def epochIs(self, epoch):
    """Sets the internal epoch value.

    If this is set to 0, time.time() will be used to get the epoch. Any value
    higher than 0 will cause the job queue's epoch to be stepped manually by
    calls to epochIs(), and will no longer follow time.time().

    Args:
      epoch: epoch value (in seconds)

    Raises:
      exc.RangeException if epoch is non-zero and less than current internal epoch.
    """
    epoch = float(epoch)
    if epoch != 0 and epoch < self._epoch:
      raise exc.RangeException
    self._epoch = epoch

  def job(self, name):
    """Access a job in the job queue by name.

    Args:
      name: job name

    Return:
      Job object, or None if not found
    """
    for job in self._queue:
      if job.name() == name:
        return job
    return None

  def jobIs(self, job):
    """Add a new job to the job queue.

    Args:
      job: Job object

    Raises:
      exc.NameInUseException if a job of the same name already exists in queue
    """
    if self.job(job.name()) is not None:
      # XXX need logging
      raise exc.NameInUseException
    for idx, j in enumerate(self._queue):
      if j.epoch() > job.epoch():
        self._queue.insert(idx, job)
        break
    else:
      self._queue.append(job)

  def jobDel(self, name):
    """Remove a job specified by name.

    Args:
      name: name of job to remove.

    Returns:
      Job object if successful.

    Raises:
      exc.NameNotFoundException if named job does not exist
    """
    for idx, job in enumerate(self._queue):
      if job.name() == name:
        deletedJob = self._queue[idx]
        del self._queue[idx]
        return deletedJob
    # XXX need logging
    raise exc.NameNotFoundException

  def jobNew(self, name, func, args=None, delay=0, periodic=False):
    """Add a new job to the job queue.

    Args:
      name: name to assign to this job
      func: function reference to run
      args: list of arguments to pass to the function
      delay: deadline from now in seconds
      periodic: automatically re-enqueue this job when it runs
    """
    newJob = Job(name, func, delay=delay, args=args, periodic=periodic)
    self.jobIs(newJob)

  def hasNextJob(self):
    """Checks to see if a job is ready to run.

    Returns:
      True or False
    """
    if not self._queue or self._queue[0].epoch() > self.epoch():
      return False
    else:
      return True

  def nextJob(self):
    """Gets next job in the queue if one is available.

    Returns:
      Job object of next job in the queue, or None if none are due or available.
    """
    if not self.hasNextJob():
      return None
    job = self._queue.pop(0)
    if job.periodic():
      self.jobNew(job.name(), job.func(), args=job.args(), delay=job.delay(),
                  periodic=job.periodic())
    return job
