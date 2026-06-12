"""Action outcomes for ROS 2 integration tests."""

from enum import Enum, auto


class ActionOutcome(Enum):
    """Outcome for the mock action server to use when a goal is received."""

    SUCCEED = auto()  # Accept the goal and call goal_handle.succeed()
    ABORT = auto()  # Accept the goal and call goal_handle.abort()
    REJECT = auto()  # Reject the goal; execute callback is never called
    CANCEL = auto()  # Accept the goal and call goal_handle.canceled() (server-side cancel)
