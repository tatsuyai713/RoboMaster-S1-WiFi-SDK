"""Event primitives exposed by the official RoboMaster SDK."""

from collections import defaultdict, namedtuple


class Handler(namedtuple("Handler", ("obj", "name", "f"))):
    __slots__ = ()


class Dispatcher:
    def __init__(self):
        self._dispatcher_handlers = defaultdict(list)

    def add_handler(self, obj, name, f):
        handler = Handler(obj, name, f)
        self._dispatcher_handlers[name] = handler
        return handler

    def remove_handler(self, name):
        del self._dispatcher_handlers[name]

    def dispatch(self, msg, **kw):
        for handler in tuple(self._dispatcher_handlers.values()):
            handler.f(handler.obj, msg)


__all__ = ["Handler", "Dispatcher"]
