"""
Tests for TestActionClient and MockActionServer.

The tests use the `example_interfaces/Fibonacci` action interface. Both helper
classes are tested against eachother.
"""

import threading

import pytest
from action_msgs.msg import GoalStatus
from example_interfaces.action import Fibonacci

from ros2_test_utils import ActionOutcome


@pytest.fixture
def fibonacci_test_data() -> tuple[int, list[Fibonacci.Feedback], Fibonacci.Result]:
    order = 4
    feedback = [
        Fibonacci.Feedback(sequence=[0, 1, 1]),
        Fibonacci.Feedback(sequence=[0, 1, 1, 2]),
        Fibonacci.Feedback(sequence=[0, 1, 1, 2, 3]),
    ]
    result = Fibonacci.Result(sequence=[0, 1, 1, 2, 3])

    # typos in the keyword can make the data be swallowed without an error
    assert all(len(fb.sequence) > 0 for fb in feedback)
    assert len(result.sequence) > 0

    return order, feedback, result


def test_send_goal_succeeds(fibonacci_server, fibonacci_client, fibonacci_test_data):
    order, feedback, result = fibonacci_test_data
    fibonacci_server.set_feedback(feedback)
    fibonacci_server.set_result(result)

    response = fibonacci_client.send_goal(Fibonacci.Goal(order=order))

    # send_goal() should be blocking and only return after any goal is processed
    assert not fibonacci_client.is_goal_in_flight

    # verify that the goal was accepted
    assert fibonacci_client.was_last_goal_accepted

    # only a single goal should have been processed by the client
    assert fibonacci_client.goal_count == 1

    # check if the feedback, result and outcome is as expected
    assert fibonacci_client.received_feedback == feedback
    assert fibonacci_client.last_result == result
    assert response.status == GoalStatus.STATUS_SUCCEEDED


def test_send_goal_aborts(fibonacci_server, fibonacci_client):
    fibonacci_server.set_outcome(ActionOutcome.ABORT)

    response = fibonacci_client.send_goal(Fibonacci.Goal())

    # send_goal() should be blocking and only return after any goal is processed
    assert not fibonacci_client.is_goal_in_flight

    # verify that the goal was accepted
    assert fibonacci_client.was_last_goal_accepted

    # only a single goal should have been processed by the client
    assert fibonacci_client.goal_count == 1

    # check if the feedback, result and outcome is as expected
    assert fibonacci_client.received_feedback == []
    assert fibonacci_client.last_result == Fibonacci.Result()
    assert response.status == GoalStatus.STATUS_ABORTED


def test_send_goal_rejected_returns_none(fibonacci_server, fibonacci_client):
    fibonacci_server.set_outcome(ActionOutcome.REJECT)

    response = fibonacci_client.send_goal(Fibonacci.Goal())

    # send_goal() should be blocking and only return after any goal is processed
    assert not fibonacci_client.is_goal_in_flight

    # verify that the goal was rejected
    assert response is None
    assert not fibonacci_client.was_last_goal_accepted

    # no goal should have been processed by the client
    assert fibonacci_client.goal_count == 0

    # check if the feedback, result and outcome is as expected
    assert fibonacci_client.last_feedback is None
    assert fibonacci_client.last_result is None
    assert fibonacci_client.last_result_status is None


def test_send_and_cancel_goal(fibonacci_server, fibonacci_client):
    fibonacci_server.set_outcome(ActionOutcome.CANCEL)
    fibonacci_server.set_execute_delay(5.0)

    response_container = []

    def _send_goal():
        response_container.append(fibonacci_client.send_goal(Fibonacci.Goal()))

    thread = threading.Thread(target=_send_goal)
    thread.start()

    # can only cancel if the goal is processed
    fibonacci_client.wait_for_goal_in_flight(timeout=5.0)

    # verify that the goal was accepted
    assert fibonacci_client.was_last_goal_accepted

    # only a single goal should have been processed by the client
    assert fibonacci_client.goal_count == 1

    assert fibonacci_client.cancel_current_goal()

    # check if the server finished
    thread.join(timeout=2.0)
    assert not thread.is_alive(), "send_goal did not return after cancel"

    # goal should be done processing
    assert not fibonacci_client.is_goal_in_flight

    assert fibonacci_client.received_feedback == []
    assert fibonacci_client.last_result == Fibonacci.Result()
    assert response_container[0].status == GoalStatus.STATUS_CANCELED


def test_user_feedback_callback_still_called(
    fibonacci_server, fibonacci_client, fibonacci_test_data
):
    order, feedback, _ = fibonacci_test_data
    fibonacci_server.set_feedback(feedback)

    user_received = []
    response = fibonacci_client.send_goal(
        Fibonacci.Goal(order=order),
        feedback_callback=lambda fb_msg: user_received.append(fb_msg.feedback),
    )

    assert fibonacci_client.received_feedback == feedback
    assert user_received == feedback
    assert response.status == GoalStatus.STATUS_SUCCEEDED


def test_feedback_does_not_accumulate_across_goals(
    fibonacci_server, fibonacci_client, fibonacci_test_data
):
    _, feedback, _ = fibonacci_test_data
    fibonacci_server.set_feedback(feedback)

    fibonacci_client.send_goal(Fibonacci.Goal())
    fibonacci_client.send_goal(Fibonacci.Goal())

    assert fibonacci_client.received_feedback == feedback
    assert fibonacci_client.goal_count == 2


def test_last_result_updated_after_each_goal(fibonacci_server, fibonacci_client):
    result_1 = Fibonacci.Result(sequence=[0, 1, 1])
    result_2 = Fibonacci.Result(sequence=[0, 1, 1, 2])
    assert result_1 != result_2

    fibonacci_server.set_result(result_1)
    response_1 = fibonacci_client.send_goal(Fibonacci.Goal())

    assert response_1.status == GoalStatus.STATUS_SUCCEEDED
    assert fibonacci_client.last_result == result_1

    fibonacci_server.set_result(result_2)
    response_2 = fibonacci_client.send_goal(Fibonacci.Goal())

    assert response_2.status == GoalStatus.STATUS_SUCCEEDED
    assert fibonacci_client.last_result == result_2

    assert fibonacci_client.goal_count == 2


def test_goal_count_not_incremented_on_rejection(fibonacci_server, fibonacci_client):
    fibonacci_client.send_goal(Fibonacci.Goal())
    assert fibonacci_client.goal_count == 1

    fibonacci_server.set_outcome(ActionOutcome.REJECT)
    fibonacci_client.send_goal(Fibonacci.Goal())
    assert fibonacci_client.goal_count == 1


def test_initial_state(fibonacci_client):
    assert fibonacci_client.received_feedback == []
    assert fibonacci_client.last_feedback is None
    assert fibonacci_client.last_result is None
    assert fibonacci_client.last_result_status is None
    assert fibonacci_client.goal_count == 0
    assert not fibonacci_client.is_goal_in_flight
    assert fibonacci_client.current_goal_status is None
    assert fibonacci_client.last_goal_handle is None
    assert not fibonacci_client.was_last_goal_accepted


def test_reset_clears_state(fibonacci_server, fibonacci_client, fibonacci_test_data):
    order, feedback, result = fibonacci_test_data

    fibonacci_server.set_feedback(feedback)
    fibonacci_server.set_result(result)
    fibonacci_client.send_goal(Fibonacci.Goal(order=order))

    assert fibonacci_client.received_feedback == feedback
    assert fibonacci_client.last_feedback == feedback[-1]
    assert fibonacci_client.last_result == result
    assert fibonacci_client.last_result_status == GoalStatus.STATUS_SUCCEEDED
    assert fibonacci_client.goal_count == 1
    assert fibonacci_client.current_goal_status is None
    assert fibonacci_client.last_goal_handle is not None
    assert fibonacci_client.was_last_goal_accepted

    fibonacci_client.reset()

    assert fibonacci_client.received_feedback == []
    assert fibonacci_client.last_feedback is None
    assert fibonacci_client.last_result is None
    assert fibonacci_client.last_result_status is None
    assert fibonacci_client.goal_count == 0
    assert not fibonacci_client.is_goal_in_flight
    assert fibonacci_client.current_goal_status is None
    assert fibonacci_client.last_goal_handle is None
    assert not fibonacci_client.was_last_goal_accepted


def test_reset_raises_when_goal_in_flight(fibonacci_server, fibonacci_client):
    fibonacci_server.set_execute_delay(5.0)

    thread = threading.Thread(target=lambda: fibonacci_client.send_goal(Fibonacci.Goal()))
    thread.start()

    fibonacci_client.wait_for_goal_in_flight(timeout=5.0)

    with pytest.raises(RuntimeError, match="goal is in flight"):
        fibonacci_client.reset()

    fibonacci_client.cancel_current_goal()
    thread.join(timeout=2.0)


def test_cancel_when_no_goal_in_flight(fibonacci_client):
    result = fibonacci_client.cancel_current_goal()
    assert result is False
