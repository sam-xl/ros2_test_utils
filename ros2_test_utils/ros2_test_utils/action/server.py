"""Action server for ROS 2 integration tests."""

import itertools
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.node import Node

from ros2_test_utils.action.outcome import ActionOutcome

_CANCEL_POLL_INTERVAL = 0.05


class MockActionServer:
    """
    Configurable ROS2 action server for use in tests.

    Attach to an existing node, configure the desired behavior, then assert on
    the goals received after your code-under-test has run.

    Basic usage::

        server = MockActionServer(node, MyAction, '/my_action')

        server.set_outcome(ActionOutcome.SUCCEED)
        server.set_result(MyAction.Result(value=42))

        # ... trigger the client ...

        assert server.goal_count == 1
        assert server.last_goal_request.target == expected_target

    Call reset() between test cases and destroy() in teardown.
    """

    def __init__(
        self,
        node: Node,
        action_type: Any,
        action_name: str,
        *,
        outcome: ActionOutcome = ActionOutcome.SUCCEED,
        result: Any | None = None,
        feedback: Any | Sequence[Any] | None = None,
        execute_delay: float = 0.0,
        feedback_delay: float | Sequence[float] = 0.0,
        execute_callback: Callable[[ServerGoalHandle], Any] | None = None,
    ) -> None:
        """Create a MockActionServer attached to node for the given action type and name."""
        self._action_type = action_type
        self._outcome = outcome
        self._result = result
        self._feedback: Sequence[Any] = (
            [feedback]
            if feedback is not None and not isinstance(feedback, Sequence)
            else (feedback or [])
        )
        self._feedback_delay: float | Sequence[float] = feedback_delay
        self._execute_delay = execute_delay
        self._custom_execute_callback = execute_callback

        self._logger = node.get_logger()
        self._lock = threading.Lock()
        self._received_goals: list[Any] = []
        self._was_cancelled = False

        self._server = ActionServer(
            node,
            action_type,
            action_name,
            self._execute,
            goal_callback=self._on_goal,
            cancel_callback=self._on_cancel,
        )

    def set_outcome(self, outcome: ActionOutcome) -> None:
        """Set the outcome the server will report when an action finishes executing."""
        self._outcome = outcome

    def set_result(self, result: Any) -> None:
        """Set the result the server will return when an action finishes executing."""
        self._result = result

    def set_execute_delay(self, seconds: float) -> None:
        """
        Set the delay (in seconds) to wait before returning the final result.

        The delay begins only after all feedback messages have been published.
        """
        self._execute_delay = seconds

    def set_feedback(self, sequence: Any | Sequence[Any]) -> None:
        """
        Set the feedback messages to publish during goal execution.

        Accepts a single feedback message or a replayable sequence (list, tuple, etc.).
        Generators and other one-shot iterators are not supported, as the sequence must
        be replayable across multiple goal executions.
        """
        self._feedback = [sequence] if not isinstance(sequence, Sequence) else sequence

    def set_feedback_delay(self, delay: float | Sequence[float]) -> None:
        """
        Set the delay (in seconds) applied after each feedback message is published.

        A single float applies the same delay after every message. A sequence of floats
        applies delays per message in order: if the sequence is shorter than the feedback
        the remaining messages are published without delay; if it is longer the excess
        values are ignored.
        """
        self._feedback_delay = delay

    def set_execute_callback(self, callback: Callable[[ServerGoalHandle], Any] | None) -> None:
        """
        Set a custom callback to run instead of the default execute logic.

        The callback receives the goal handle and must return a result. When set, outcome,
        result, feedback, and delay configuration are all bypassed.
        """
        self._custom_execute_callback = callback

    @property
    def received_goals(self) -> list[Any]:
        """Thread-safe snapshot of goal requests received since the last reset."""
        with self._lock:
            return list(self._received_goals)

    @property
    def last_goal_request(self) -> Any | None:
        """The most recently received goal request, or None if no goals have been received."""
        with self._lock:
            return self._received_goals[-1] if self._received_goals else None

    @property
    def goal_count(self) -> int:
        """Number of goal requests received since the last reset."""
        with self._lock:
            return len(self._received_goals)

    @property
    def was_cancelled(self) -> bool:
        """True if any goal received since the last reset was cancelled by the client."""
        with self._lock:
            return self._was_cancelled

    def reset(self) -> None:
        """Clear received goals and cancel state."""
        with self._lock:
            self._received_goals.clear()
            self._was_cancelled = False

    def destroy(self) -> None:
        """Destroy the underlying ActionServer."""
        self._server.destroy()

    def _warn_if_unexpected_cancel(self) -> None:
        if self._outcome != ActionOutcome.CANCEL:
            self._logger.warning(
                f"Goal was client-cancelled during execution, but outcome was {self._outcome!r}"
            )

    def _on_goal(self, goal_request) -> GoalResponse:
        if self._outcome == ActionOutcome.REJECT:
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_cancel(self, goal_handle) -> CancelResponse:
        with self._lock:
            self._was_cancelled = True
        return CancelResponse.ACCEPT

    def _execute(self, goal_handle: ServerGoalHandle) -> Any:
        with self._lock:
            self._received_goals.append(goal_handle.request)

        if self._custom_execute_callback is not None:
            return self._custom_execute_callback(goal_handle)

        delays = (
            itertools.chain(self._feedback_delay, itertools.repeat(0.0))
            if isinstance(self._feedback_delay, Iterable)
            else itertools.repeat(self._feedback_delay)
        )
        for feedback, delay in zip(self._feedback, delays, strict=False):
            if goal_handle.is_cancel_requested:
                self._warn_if_unexpected_cancel()
                goal_handle.canceled()
                return self._action_type.Result()
            goal_handle.publish_feedback(feedback)
            if delay > 0.0:
                time.sleep(delay)

        if self._execute_delay > 0.0:
            elapsed = 0.0
            step = min(_CANCEL_POLL_INTERVAL, self._execute_delay)
            while elapsed < self._execute_delay:
                if goal_handle.is_cancel_requested:
                    self._warn_if_unexpected_cancel()
                    goal_handle.canceled()
                    return self._action_type.Result()
                time.sleep(step)
                elapsed += step

        result = self._result if self._result is not None else self._action_type.Result()

        match self._outcome:
            case ActionOutcome.SUCCEED:
                goal_handle.succeed()
            case ActionOutcome.ABORT:
                goal_handle.abort()
            case ActionOutcome.CANCEL:
                if not goal_handle.is_cancel_requested:
                    raise AssertionError(
                        "ActionOutcome.CANCEL requires the client to send a cancel request"
                    )
                goal_handle.canceled()
            case _:
                # REJECT is filtered in _on_goal; no other outcome should reach here.
                raise AssertionError(f"Unhandled outcome in execute: {self._outcome!r}")

        return result
