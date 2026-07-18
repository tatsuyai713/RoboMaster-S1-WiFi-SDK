from __future__ import annotations


class RoboMasterError(Exception):
    pass


class ConnectionError(RoboMasterError):
    pass


class TimeoutError(RoboMasterError):
    pass


class UnsupportedError(RoboMasterError):
    pass
