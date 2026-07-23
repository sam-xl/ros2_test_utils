"""Action client for ROS 2 integration tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from rclpy.action import ActionClient
from rclpy.action.client import ClientGoalHandle
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.task import Future

_POLL_INTERVAL = 0.05


class TestActionClient:
    """
    Inspectable ROS2 action client for use in tests.

    Wraps ActionClient with a blocking send_goal(), automatic feedback
    collection, and cancel support.  Use this when the code under test is
    an action server.

    The node must be spinning on a MultiThreadedExecutor before calling
    send_goal() or send_goal_async().

    Basic usage::

        client = TestActionClient(node, MyAction, '/my_action')
        client.wait_for_server()

        response = client.send_goal(MyAction.Goal(target=x))

        assert response.status == GoalStatus.STATUS_SUCCEEDED
        assert client.last_feedback.progress == 1.0
    """

    def __init__(self, node: Node, action_type: Any, action_name: str) -> None:
        """Create a TestActionClient attached to node for the given action type and name."""
        if node.executor is None:
            raise RuntimeError("Node has not been added to an executor.")

        executor = node.executor
        if not isinstance(executor, MultiThreadedExecutor):
            executor_type = type(executor).__name__
            raise RuntimeError(
                f"TestActionClient requires a MultiThreadedExecutor. Instead got {executor_type}",
            )

        self._node = node
        self._action_type = action_type
        self._client = ActionClient(node, action_type, action_name)

        self._lock = threading.Lock()
        self._received_feedback: list[Any] = []
        self._last_get_result_response: Any | None = None
        self._goal_count: int = 0
        self._current_goal_handle: ClientGoalHandle | None = None
        self._last_goal_handle: ClientGoalHandle | None = None
        self._async_result_future: Any | None = None

    def wait_for_server(self, timeout_sec: float = 5.0) -> bool:
        """Block until the server is available. Returns True on success, False on timeout."""
        return self._client.wait_for_server(timeout_sec=timeout_sec)

    def send_goal(
        self,
        goal: Any,
        *,
        feedback_callback: Callable[[Any], None] | None = None,
        timeout_sec: float = 5.0,
    ) -> Any | None:
        """
        Send a goal and block until the result arrives.

        Returns the GetResult_Response (with .status and .result), or None
        if the goal was rejected.
        """
        # use getattr to default to True for ROS 2 Humble as 'is_spinning' is not present yet.
        # instead the timeout will be hit
        is_spinning = getattr(self._node.executor, "is_spinning", True)

        if not is_spinning:
            raise RuntimeError(
                "TestActionClient requires the executor to be spinning before calling send_goal()",
            )

        with self._lock:
            self._received_feedback.clear()

        combined_cb = self._make_feedback_cb(feedback_callback)
        goal_future = self._client.send_goal_async(goal, feedback_callback=combined_cb)
        deadline = time.monotonic() + timeout_sec

        while not goal_future.done():
            assert time.monotonic() < deadline, "Timed out waiting for goal acceptance"
            time.sleep(_POLL_INTERVAL)

        goal_handle = goal_future.result()

        if not goal_handle.accepted:
            return None

        with self._lock:
            self._goal_count += 1
            self._current_goal_handle = goal_handle
            self._last_goal_handle = goal_handle

        result_future = goal_handle.get_result_async()
        while not result_future.done():
            assert time.monotonic() < deadline, "Timed out waiting for result"
            time.sleep(_POLL_INTERVAL)

        response = result_future.result()
        with self._lock:
            self._last_get_result_response = response
            self._current_goal_handle = None

        return response

    def send_goal_async(
        self,
        goal: Any,
        *,
        feedback_callback: Callable[[Any], None] | None = None,
    ) -> Future:
        """
        Send a goal and return immediately with a Future[ClientGoalHandle].

        Feedback is still collected internally.  Use this when you need to
        cancel mid-execution from the same thread as send_goal would block.
        """
        with self._lock:
            self._received_feedback.clear()

        combined_cb = self._make_feedback_cb(feedback_callback)
        future = self._client.send_goal_async(goal, feedback_callback=combined_cb)

        def _on_result(result_future):
            with self._lock:
                self._last_get_result_response = result_future.result()
                self._current_goal_handle = None

        def _on_accepted(goal_future):
            handle = goal_future.result()
            if handle.accepted:
                with self._lock:
                    self._goal_count += 1
                    self._current_goal_handle = handle
                    self._last_goal_handle = handle
                    self._async_result_future = handle.get_result_async()
                    self._async_result_future.add_done_callback(_on_result)

        future.add_done_callback(_on_accepted)
        return future

    def wait_for_goal_in_flight(self, timeout_sec: float = 5.0) -> None:
        """Block until a goal has been accepted and is in flight."""
        deadline = time.monotonic() + timeout_sec
        while not self.is_goal_in_flight:
            assert time.monotonic() < deadline, "Timed out waiting for goal to be in flight"
            time.sleep(_POLL_INTERVAL)

    def wait_for_async_result(self, timeout_sec: float = 5.0) -> Any:
        """Block until the result of the most recent async goal arrives and return it."""
        with self._lock:
            future = self._async_result_future
        if future is None:
            raise RuntimeError("wait_for_async_result called before any async goal was sent")

        deadline = time.monotonic() + timeout_sec
        while not future.done():
            assert time.monotonic() < deadline, "Timed out waiting for async result"
            time.sleep(_POLL_INTERVAL)
        return future.result()

    def cancel_current_goal(self, timeout_sec: float = 5.0) -> bool:
        """
        Cancel the goal currently in flight via send_goal().

        Returns True if a cancel request was sent, False if there was no
        goal in flight.  Call from a separate thread while send_goal() is
        blocking.
        """
        with self._lock:
            handle = self._current_goal_handle

        if handle is None:
            return False

        cancel_future = handle.cancel_goal_async()
        deadline = time.monotonic() + timeout_sec
        while not cancel_future.done():
            assert time.monotonic() < deadline, "Timed out waiting for cancel response"
            time.sleep(_POLL_INTERVAL)

        return True

    @property
    def received_feedback(self) -> list[Any]:
        """
        Thread-safe snapshot of all feedback received for the current or last goal.

        Cleared at the start of each send_goal() or send_goal_async() call.
        """
        with self._lock:
            return list(self._received_feedback)

    @property
    def last_feedback(self) -> Any | None:
        """The most recent feedback message, or None if no feedback received."""
        with self._lock:
            return self._received_feedback[-1] if self._received_feedback else None

    @property
    def last_result(self) -> Any | None:
        """The result field of the last GetResult response, or None."""
        with self._lock:
            return (
                self._last_get_result_response.result if self._last_get_result_response else None
            )

    @property
    def last_result_status(self) -> int | None:
        """GoalStatus of the last completed goal, or None."""
        with self._lock:
            return (
                self._last_get_result_response.status if self._last_get_result_response else None
            )

    @property
    def goal_count(self) -> int:
        """Number of goals accepted by the server (rejected goals are not counted)."""
        with self._lock:
            return self._goal_count

    @property
    def is_goal_in_flight(self) -> bool:
        """True while a goal has been accepted and its result has not yet arrived."""
        with self._lock:
            return self._current_goal_handle is not None

    @property
    def current_goal_status(self) -> int | None:
        """GoalStatus of the in-flight goal, or None if no goal is in flight."""
        with self._lock:
            handle = self._current_goal_handle
            return handle.status if handle is not None else None

    @property
    def last_goal_handle(self) -> ClientGoalHandle | None:
        """The ClientGoalHandle for the last accepted goal, retained after completion."""
        with self._lock:
            return self._last_goal_handle

    @property
    def was_last_goal_accepted(self) -> bool:
        """True if the last sent goal was accepted (False if rejected or no goal sent)."""
        with self._lock:
            return self._last_goal_handle is not None and self._last_goal_handle.accepted

    def reset(self) -> None:
        """Clear all state. Raises RuntimeError if a goal is still in flight."""
        with self._lock:
            if self._current_goal_handle is not None:
                raise RuntimeError(
                    "reset() called while a goal is in flight. "
                    "Wait for the goal to complete or cancel it before resetting."
                )
            self._received_feedback.clear()
            self._last_get_result_response = None
            self._goal_count = 0
            self._last_goal_handle = None

    def destroy(self) -> None:
        """Destroy the underlying ActionClient."""
        self._client.destroy()

    def _make_feedback_cb(
        self, user_callback: Callable[[Any], None] | None
    ) -> Callable[[Any], None]:
        def _cb(feedback_msg: Any) -> None:
            with self._lock:
                self._received_feedback.append(feedback_msg.feedback)
            if user_callback is not None:
                user_callback(feedback_msg)

        return _cb
