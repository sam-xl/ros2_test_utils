"""Topic subscriber for ROS 2 integration tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from rclpy.node import Node
from rclpy.qos import QoSProfile

_POLL_INTERVAL = 0.05


class TestSubscriber:
    """
    Inspectable ROS2 subscriber for use in tests.

    Collects every message received on a topic. Use this when the code under
    test publishes on that topic.

    The node must be spinning (e.g. on the ``test_node`` fixture's executor)
    for messages to arrive.

    Basic usage::

        subscriber = TestSubscriber(node, String, '/chatter')
        subscriber.wait_for_publisher()

        # ... trigger the publisher ...

        message = subscriber.wait_for_message(lambda m: m.data == 'hello')
        assert subscriber.message_count == 1
    """

    # Not a test class, despite its name, for pytest collecting from modules that import it.
    __test__ = False

    def __init__(
        self,
        node: Node,
        msg_type: Any,
        topic: str,
        qos_profile: QoSProfile | int = 10,
    ) -> None:
        """Create a TestSubscriber attached to node for the given message type and topic."""
        self._node = node
        self._lock = threading.Lock()
        self._received_messages: list[Any] = []
        self._subscription = node.create_subscription(
            msg_type, topic, self._on_message, qos_profile
        )

    def wait_for_publisher(self, timeout_sec: float = 5.0) -> bool:
        """Block until a publisher matches. Returns True on success, False on timeout."""
        deadline = time.monotonic() + timeout_sec
        while self._subscription.get_publisher_count() == 0:
            if time.monotonic() > deadline:
                return False
            time.sleep(_POLL_INTERVAL)
        return True

    def wait_for_message(
        self,
        predicate: Callable[[Any], bool] | None = None,
        timeout_sec: float = 5.0,
    ) -> Any:
        """
        Block until a message matching predicate has been received and return it.

        Messages received before the call count too, so a message that arrived
        early is not missed. Without a predicate, any message matches.
        """
        deadline = time.monotonic() + timeout_sec
        while (message := self._find(predicate)) is None:
            assert time.monotonic() < deadline, "Timed out waiting for message"
            time.sleep(_POLL_INTERVAL)
        return message

    @property
    def received_messages(self) -> list[Any]:
        """Thread-safe snapshot of the messages received since the last reset."""
        with self._lock:
            return list(self._received_messages)

    @property
    def last_message(self) -> Any | None:
        """The most recently received message, or None if no message was received."""
        with self._lock:
            return self._received_messages[-1] if self._received_messages else None

    @property
    def message_count(self) -> int:
        """Number of messages received since the last reset."""
        with self._lock:
            return len(self._received_messages)

    def reset(self) -> None:
        """Clear the received messages."""
        with self._lock:
            self._received_messages.clear()

    def destroy(self) -> None:
        """Destroy the underlying subscription."""
        self._node.destroy_subscription(self._subscription)

    def _find(self, predicate: Callable[[Any], bool] | None) -> Any | None:
        return next(
            (m for m in self.received_messages if predicate is None or predicate(m)),
            None,
        )

    def _on_message(self, message: Any) -> None:
        with self._lock:
            self._received_messages.append(message)
