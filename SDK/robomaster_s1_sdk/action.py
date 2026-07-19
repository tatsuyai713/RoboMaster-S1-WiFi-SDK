from __future__ import annotations

import threading


ACTION_IDLE = "action_idle"
ACTION_RUNNING = "action_running"
ACTION_SUCCEEDED = "action_succeeded"
ACTION_FAILED = "action_failed"
ACTION_STARTED = "action_started"
ACTION_ABORTING = "action_aborting"
ACTION_ABORTED = "action_aborted"
ACTION_REJECTED = "action_rejected"
ACTION_EXCEPTION = "action_exception"
ACTION_NOW = "action_now"
ACTION_QUEUE = "action_queue"
ACTION_REQUEST = "action_request"


class Action:
    """Official-SDK-shaped state object for mapped S1 commands."""

    def __init__(self, completed: bool = True, accepted: bool = True) -> None:
        self.accepted = bool(accepted)
        self._action_id = -1
        self._state = (
            ACTION_SUCCEEDED
            if completed and self.accepted
            else ACTION_REJECTED
            if completed
            else ACTION_IDLE
        )
        self._percent = 100 if completed and self.accepted else 0
        self._failure_reason = 0 if self.accepted else -1
        self._event = threading.Event()
        self._push_proto_cls = object
        self._obj = None
        self._on_state_changed = None
        if self.is_completed:
            self._event.set()

    @property
    def target(self) -> int:
        return 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state in {ACTION_RUNNING, ACTION_STARTED}

    @property
    def is_completed(self) -> bool:
        return self._percent == 100 or self._state in {
            ACTION_SUCCEEDED,
            ACTION_FAILED,
            ACTION_ABORTED,
            ACTION_REJECTED,
            ACTION_EXCEPTION,
        }

    @property
    def has_succeeded(self) -> bool:
        return self._state == ACTION_SUCCEEDED

    @property
    def has_failed(self) -> bool:
        return self._state == ACTION_FAILED

    @property
    def failure_reason(self):
        return self._failure_reason

    def wait_for_completed(self, timeout: float | None = None) -> bool:
        if not self._event.wait(timeout):
            return False
        return self.has_succeeded

    def make_action_key(self):
        return self._action_id

    def found_proto(self, proto) -> bool:  # noqa: ANN001
        return False

    def found_action(self, proto) -> bool:  # noqa: ANN001
        return False

    def update_from_push(self, proto) -> None:  # noqa: ANN001
        return None

    def _changeto_state(self, state: str) -> None:
        previous = self._state
        self._state = state
        if state == ACTION_SUCCEEDED:
            self._percent = 100
        if self.is_completed:
            self._event.set()
        if self._on_state_changed is not None:
            self._on_state_changed(self, previous, state)

    def _abort(self) -> None:
        self._changeto_state(ACTION_ABORTED)


class ImmediateAction(Action):
    def __init__(self, accepted: bool = True) -> None:
        super().__init__(completed=True, accepted=accepted)


class TextAction(ImmediateAction):
    pass


class ActionDispatcher:
    """Compatibility dispatcher for commands completed by their public API."""

    def __init__(self, client=None) -> None:  # noqa: ANN001
        self._client = client
        self._in_progress = {}
        self._in_progress_mutex = threading.RLock()

    @property
    def has_in_progress_actions(self) -> bool:
        with self._in_progress_mutex:
            return bool(self._in_progress)

    def initialize(self) -> bool:
        return True

    def send_action(self, action, action_type=ACTION_NOW):  # noqa: ANN001
        return action
