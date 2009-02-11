import socket


class ClientControlBase(object):
  def _eta_time(self, size, speed):
    if speed == 0:
      return 0, 0

    eta = size * 1024 / float(speed)  # seconds
    eta_h = int(eta / 3600)
    eta_m = int((eta % 3600) / 60)

    return eta_h, eta_m

  def _eta(self, status):
    try:
      current_item_size, queue_size, queue_items, speed = status
    except socket.error:
      return None

    total_size = current_item_size + queue_size
    eta_str = ""

    if speed > 0:
      total_eta_h, total_eta_m = self._eta_time(total_size, speed)
      cur_eta_h, cur_eta_m = self._eta_time(current_item_size, speed)
      eta_str = " [%dh%dm / %dh%dm]" % (cur_eta_h, cur_eta_m,
                                        total_eta_h, total_eta_m)

    plural = queue_items == 1 and "item" or "items"
    msg = "%d MB + %d MB queued (%d %s) @ %d KB/s%s"

    return msg % (current_item_size, queue_size,
                  queue_items, plural, speed, eta_str)

  def _queue_size(self, status):
    try:
      current_item_size, queue_size, queue_items, speed = status
    except socket.error:
      return 0

    total_size = current_item_size + queue_size
    return total_size
