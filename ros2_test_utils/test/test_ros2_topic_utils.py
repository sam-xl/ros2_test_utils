"""
Tests for TestSubscriber and the make_test_subscriber / make_test_publisher fixtures.

The tests use the `example_interfaces/Int32` message. Each fixture waits for the
other side of the topic, so every test creates one side directly on `test_node`.
"""

import pytest
from example_interfaces.msg import Int32
from rclpy.qos import DurabilityPolicy, QoSProfile

from ros2_test_utils import TestSubscriber

TOPIC = "/numbers"


@pytest.fixture
def publisher(test_node):
    publisher = test_node.create_publisher(Int32, TOPIC, 10)
    yield publisher
    test_node.destroy_publisher(publisher)


@pytest.fixture
def subscriber(publisher, make_test_subscriber):  # noqa: ARG001
    # Requests a publisher to ensure it exists first: make_test_subscriber waits for one.
    return make_test_subscriber(Int32, TOPIC)


def publish(publisher, numbers):
    for number in numbers:
        publisher.publish(Int32(data=number))


def test_subscriber_collects_messages(publisher, subscriber):
    publish(publisher, [0, 1, 2])

    assert subscriber.wait_for_message(lambda m: m.data == 2) == Int32(data=2)
    assert subscriber.received_messages == [Int32(data=n) for n in (0, 1, 2)]
    assert subscriber.last_message == Int32(data=2)
    assert subscriber.message_count == 3


def test_wait_for_message_matches_an_earlier_message(publisher, subscriber):
    publish(publisher, [0, 1])
    subscriber.wait_for_message(lambda m: m.data == 1)

    assert subscriber.wait_for_message(lambda m: m.data == 0, timeout_sec=0.0) == Int32(data=0)


def test_wait_for_message_without_predicate_matches_any(publisher, subscriber):
    publish(publisher, [7])

    assert subscriber.wait_for_message() == Int32(data=7)


def test_wait_for_message_times_out(publisher, subscriber):
    publish(publisher, [0])

    with pytest.raises(AssertionError, match="Timed out waiting for message"):
        subscriber.wait_for_message(lambda m: m.data == 1, timeout_sec=0.5)


def test_reset_clears_messages(publisher, subscriber):
    publish(publisher, [0])
    subscriber.wait_for_message()

    subscriber.reset()

    assert subscriber.received_messages == []
    assert subscriber.last_message is None
    assert subscriber.message_count == 0


def test_make_test_subscriber_requires_a_publisher(make_test_subscriber):
    with pytest.raises(AssertionError, match="No publisher on '/numbers'"):
        make_test_subscriber(Int32, TOPIC, timeout_sec=0.5)


def test_make_test_publisher_waits_for_the_subscription(test_node, make_test_publisher):
    subscriber = TestSubscriber(test_node, Int32, TOPIC)

    # Published right away: without the wait, the message could be sent before
    # the publisher discovered the subscription, and be lost.
    make_test_publisher(Int32, TOPIC).publish(Int32(data=3))

    assert subscriber.wait_for_message() == Int32(data=3)
    subscriber.destroy()


def test_make_test_publisher_requires_a_subscription(make_test_publisher):
    with pytest.raises(AssertionError, match="No subscription on '/numbers'"):
        make_test_publisher(Int32, TOPIC, timeout_sec=0.5)


def test_qos_profile_reaches_both_fixtures(test_node, make_test_publisher, make_test_subscriber):
    latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    subscriber = TestSubscriber(test_node, Int32, TOPIC, latched)
    make_test_publisher(Int32, TOPIC, qos_profile=latched).publish(Int32(data=4))
    subscriber.destroy()

    # Joins after the message was sent, so only a transient-local subscription gets it.
    late = make_test_subscriber(Int32, TOPIC, qos_profile=latched)

    assert late.wait_for_message() == Int32(data=4)
