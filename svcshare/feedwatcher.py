import os
import pickle
import re
import time
import xmlrpclib

from svcshare import feedparser

AGE_THRESHOLD = 86400 * 5  # ignore posts older than this many seconds


class Feedwatcher(object):
  def __init__(self, filename, require_nfo=True):
    self._datafile = filename
    self._require_nfo = require_nfo
    self._posts = {}
    self.load()

  def save(self):
    """Save the posts to a file.
    """
    fd = open(self._datafile, "w+")
    pickle.dump(self._posts, fd)
    fd.close()

  def load(self):
    """Load the posts from a file.
    """
    if not os.path.exists(self._datafile):
      self.save()
      return
    fd = open(self._datafile, "r")
    self._posts = pickle.load(fd)
    fd.close()

  def time_delta(self, t1, t2):
    """Find delta in seconds between two 9-tuple times. Assumes t1 < t2.
    """
    return int(time.strftime("%s", t2)) - int(time.strftime("%s", t1))

  def extract_nzbid(self, url):
    m = re.search(r"\/(\d+)/?$", url)
    if m:
      return int(m.group(1))
    else:
      return None

  def _is_new(self, entry, age_threshold=AGE_THRESHOLD):
    """Returns True if the given entry is new.

    Returns:
      True if the given entry is new
    """
    postdate = entry.get("postdate") or entry.get("report_postdate")
    if not postdate:
      return True
    postdate_parsed = time.strptime(postdate,
                                    "%a, %d %b %Y %H:%M:%S %Z");  # RFC 822
    if self.time_delta(postdate_parsed, time.localtime()) > age_threshold:
      return False
    return self.extract_nzbid(entry.id) not in self._posts

  def mark_old(self, entry):
    """Mark an entry as old.
    """
    id = self.extract_nzbid(entry.id)
    if id is not None:
      self._posts[id] = True

  def poll_feed(self, feed_url):
    """Download an RSS feed and process its entries.

    Args:
      feed_url: RSS feed URL

    Returns:
      list of new newzbin entries
    """
    new_entries = []
    feed = feedparser.parse(feed_url)
    for entry in feed.entries:
      if entry is None or not self._is_new(entry):
        continue
      if (self._require_nfo and
          not entry.get("filename") and
          not entry.get("report_filename")):
        continue
      new_entries.append(entry)
    return new_entries
