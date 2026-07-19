from __future__ import annotations

from robomaster_lab_sdk.exceptions import ConnectionError, RoboMasterError, TimeoutError, UnsupportedError

SDKException = RoboMasterError
TimeOutError = TimeoutError


class OutOfRangeError(SDKException):
    pass


__all__ = ["TimeOutError"]
