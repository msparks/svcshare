import time


class JobQueue(object):
  def __init__(self):
    self._queue = []

  def add_job(self, name, epoch):
    """Add a new job to the job queue.

    Args:
      name: name of the job (string)
      epoch: Unix epoch when the job should execute (int)
    """
    job = (name, epoch)
    for idx, (n, e) in enumerate(self._queue):
      if e > epoch:
        self._queue.insert(idx, job)
        break
    else:
      self._queue.append(job)

  def has_next_job(self):
    """Checks to see if a job is ready to run.

    Returns:
      True or False
    """
    if not self._queue or self._queue[0][1] > time.time():
      return False
    else:
      return True

  def next_job(self):
    """Gets next job in the queue if one is available.

    Returns:
      Next due job in the queue, or None if none are due or available.
    """
    if not self.has_next_job():
      return None
    return self._queue.pop(0)[0]


if __name__ == "__main__":
  q = JobQueue()
  now = time.time()
  q.add_job("foo", now + 3)
  q.add_job("bar", now + 8)
  assert(q.next_job() is None)
  time.sleep(3)
  assert(q.next_job() == "foo")
  time.sleep(5)
  assert(q.next_job() == "bar")
  assert(q.has_next_job() == False)
