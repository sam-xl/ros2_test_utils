# ros2_test_utils

## Overview
This package provides a pytest plugin and utility classes for integration tests of ROS 2 interfaces. Currently this covers actions, but services and topics are planned. 

**Maintainer:** D. Kroezen (GitHub username: dave992)

Requires Python 3.10+, ROS2 Humble or later.

## Installation

### Build from source

To build from source, clone the latest version from this repository into your workspace:
```bash
git clone https://github.com/dave992/ros2_test_utils.git
```

Install the dependencies of the cloned package using rosdep:
```bash
rosdep install --from-paths src -iy
```

Finally, build all packages in the workspace:
```bash
colcon build [--merge-install] [--symlink-install]
```

## Usage

To use this package, add it as a test dependency in your package's `package.xml`:
```xml
<test_depend>ros2_test_utils</test_depend>
```

Once built or installed, the utility classes and pytest fixtures are available in your package's tests.

### Setting up your test(s) and fixtures

The recommended usage is to wrap the provided fixtures in action-type-specific fixtures in your `conftest.py`. The sections below show the pattern for both sides of an action interface.

#### Action server

When testing an action server, you can make use of the `TestActionClient` via the `make_test_client` fixture.

In your `conftest.py` define your fixtures and launch descriptions that are used in the tests.

```python
# your_package/test/conftest.py
import pytest
from example_interfaces.action import Fibonacci

# ... use launch_pytest to load your launch_description if needed ...

@pytest.fixture
def fibonacci_client(launch_description, make_test_client):
    # launch_description ensures the server is up before wait_for_server runs
    return make_test_client(Fibonacci, '/fibonacci')
```

And the tests themselves:

```python
# your_package/test/test_fibonacci_server.py
import pytest
from action_msgs.msg import GoalStatus

@pytest.mark.launch(fixture=launch_description)
def test_fibonacci_server(fibonacci_client):
    response = fibonacci_client.send_goal(Fibonacci.Goal(order=5))

    assert response.status == GoalStatus.STATUS_SUCCEEDED
    assert response.result == Fibonacci.Result(...)

# ... more tests ...
```

#### Action client

When testing an action client, use the `MockActionServer` via the `make_mock_server` fixture to stand in for the real server.

```python
# your_package/test/conftest.py
import pytest
from example_interfaces.action import Fibonacci

# ... use launch_pytest to load your launch_description if needed ...

@pytest.fixture
def fibonacci_server(make_mock_server):
    return make_mock_server(Fibonacci, '/fibonacci')
```

You can optionally pre-configure the `MockActionServer` in the fixture itself, or set it up per test as shown below.

```python
# your_package/test/test_fibonacci_client.py
def test_fibonacci_client(fibonacci_server):
    fibonacci_server.set_outcome(...)
    fibonacci_server.set_feedback(...)
    fibonacci_server.set_result(...)

    # ... configure and trigger your client under test ...

    assert fibonacci_server.goal_count == 1
    assert fibonacci_server.last_goal_request == ...

# ... more tests ...
```

## Detailed Documentation

For the full API reference — outcomes, configuration, cancellation, async goals, inspection properties, and pytest fixtures — see [docs/index.md](docs/index.md).

## Notes

- Rejected goals (`ActionOutcome.REJECT`) do not appear in `server.received_goals` and do not increment `server.goal_count` or `client.goal_count`.
- `server.was_cancelled` reflects client-initiated cancellation only. Server-side cancel (`ActionOutcome.CANCEL`) does not set it.
- Configuration setters on `MockActionServer` are not thread-safe relative to each other. Set them before sending a goal, not concurrently with one.
- Call `reset()` on either mock between test cases if you are reusing a fixture across multiple tests in the same class or parameterised test.

## Bugs & Feature Requests

Please report bugs and request features using the [Issue Tracker](https://github.com/dave992/ros2_test_utils/issues).
