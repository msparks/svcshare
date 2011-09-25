class ResourceException(Exception):
  pass


class NameInUseException(ResourceException):
  pass


class NameNotFoundException(ResourceException):
  pass


class RangeException(Exception):
  pass
