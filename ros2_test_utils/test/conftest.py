"""
Action-type-specific fixtures for the ros2_test_utils test suite.

The generic fixtures (make_mock_server, make_test_client, ros_executor, etc.)
come from ros2_test_utils, which is registered as a pytest plugin and
loaded automatically.
"""

import pytest
from example_interfaces.action import Fibonacci

ACTION_NAME = "/fibonacci"


@pytest.fixture
def fibonacci_server(make_mock_server):
    return make_mock_server(Fibonacci, ACTION_NAME)


@pytest.fixture
def fibonacci_client(fibonacci_server, make_test_client):
    return make_test_client(Fibonacci, ACTION_NAME)
