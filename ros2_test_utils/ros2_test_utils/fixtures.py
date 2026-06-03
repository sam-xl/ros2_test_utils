"""
pytest fixtures for ROS 2 integration tests.

Registered as a pytest plugin via the pytest11 entry point in setup.py, so
these fixtures are available in any package that has ros2_test_utils
installed — no import needed.

To add action-type-specific fixtures for your own package, call the generic
factory fixtures from your package's conftest.py:

    # your_package/test/conftest.py
    import pytest
    from your_interfaces.action import MyAction

    @pytest.fixture
    def my_action_server(make_mock_server):
        return make_mock_server(MyAction, '/my_action')

    @pytest.fixture
    def my_action_client(my_action_server, make_test_client):
        return make_test_client(MyAction, '/my_action')
"""

import threading

import pytest
import rclpy
from rclpy.executors import MultiThreadedExecutor

from ros2_test_utils.action.client import TestActionClient
from ros2_test_utils.action.server import MockActionServer

_WAIT_FOR_SERVER_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# ROS lifecycle
# ---------------------------------------------------------------------------


def _ros2_rclpy_init_impl():
    if rclpy.ok():
        raise RuntimeError(
            "rclpy was already initialized before the ros2_rclpy_init fixture ran. "
            "Do not call rclpy.init() before requesting this fixture."
        )

    def _guarded_init(*args, **kwargs):
        raise RuntimeError(
            "rclpy.init() was called while the ros2_rclpy_init fixture owns the session. "
            "Do not call rclpy.init() directly in tests or fixtures."
        )

    def _guarded_shutdown(*args, **kwargs):
        raise RuntimeError(
            "rclpy.shutdown() was called while the ros2_rclpy_init fixture owns the session. "
            "Do not call rclpy.shutdown() directly in tests or fixtures."
        )

    rclpy_init = rclpy.init
    rclpy_shutdown = rclpy.shutdown

    rclpy.init = _guarded_init
    rclpy.shutdown = _guarded_shutdown

    rclpy_init()

    yield

    rclpy.init = rclpy_init
    rclpy.shutdown = rclpy_shutdown

    if not rclpy.ok():
        raise RuntimeError(
            "rclpy is no longer active at ros2_rclpy_init teardown. "
            "Do not call rclpy.shutdown() directly in tests or fixtures."
        )

    rclpy.shutdown()


@pytest.fixture(scope="session")
def ros2_rclpy_init():
    """
    Initialize `rclpy` once for the entire test session.

    This fixture is used by the other provided fixtures whenever rclpy needs
    to be initialized. If you want to manage rclpy and the executor yourself,
    use the `*_on_node` fixtures instead.

    When active, this fixture guards against:
    - `rclpy.init()` being called before or during the session
    - `rclpy.shutdown()` being called during the session
    """
    yield from _ros2_rclpy_init_impl()


@pytest.fixture
def ros2_multi_threaded_executor(ros2_rclpy_init):  # noqa: ARG001
    """
    Spin a MultiThreadedExecutor in a background thread for one test.

    MultiThreadedExecutor is required: action servers need concurrent execution
    of goal/cancel service callbacks and the execute callback.
    """
    executor = MultiThreadedExecutor()
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    yield executor
    executor.shutdown(timeout_sec=2.0)


@pytest.fixture
def make_node(ros2_multi_threaded_executor):
    """
    Factory fixture for creating and registering ROS2 nodes.

    All nodes created through this fixture are automatically removed from the
    executor and destroyed at the end of the test.

    Usage::

        def test_something(make_node):
            node = make_node('my_node')
    """
    created = []

    def _factory(name: str):
        node = rclpy.create_node(name)
        ros2_multi_threaded_executor.add_node(node)
        created.append(node)
        return node

    yield _factory

    for node in created:
        ros2_multi_threaded_executor.remove_node(node)
        node.destroy_node()


@pytest.fixture
def test_node(ros2_multi_threaded_executor):
    """A ROS2 node for hosting mock servers and test clients."""
    node = rclpy.create_node("test_node")
    ros2_multi_threaded_executor.add_node(node)
    yield node
    ros2_multi_threaded_executor.remove_node(node)
    node.destroy_node()


# ---------------------------------------------------------------------------
# Action fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_mock_server(test_node):
    """
    Factory fixture for MockActionServer.

    All servers created through this fixture are automatically destroyed at the
    end of the test, regardless of pass/fail.

    Usage::

        def test_something(make_mock_server):
            server = make_mock_server(MyAction, '/my_action')
            server = make_mock_server(MyAction, '/my_action', outcome=ActionOutcome.ABORT)
    """
    created = []

    def _factory(action_type, action_name, **kwargs):
        server = MockActionServer(test_node, action_type, action_name, **kwargs)
        created.append(server)
        return server

    yield _factory

    for server in created:
        server.destroy()


@pytest.fixture
def make_test_client(test_node):
    """
    Factory fixture for TestActionClient.

    Calls wait_for_server before returning, so the server fixture must be
    created first.  All clients are automatically destroyed at end of test.

    Usage::

        def test_something(make_mock_server, make_test_client):
            server = make_mock_server(MyAction, '/my_action')
            client = make_test_client(MyAction, '/my_action')
            response = client.send_goal(MyAction.Goal(...))
    """
    created = []

    def _factory(action_type, action_name, timeout: float = _WAIT_FOR_SERVER_TIMEOUT):
        client = TestActionClient(test_node, action_type, action_name)
        created.append(client)
        assert client.wait_for_server(timeout=timeout), (
            f"Action server '{action_name}' did not become available within {timeout}s"
        )
        return client

    yield _factory

    for client in created:
        client.destroy()


@pytest.fixture
def make_mock_server_on_node(make_node):
    """
    Factory fixture for MockActionServer that creates a dedicated node per server.

    Use this instead of make_mock_server when servers must be isolated on
    separate nodes.  All servers and their nodes are destroyed at end of test.

    Usage::

        def test_something(make_mock_server_on_node):
            server = make_mock_server_on_node(MyAction, '/my_action', node_name='my_node')
    """
    created = []

    def _factory(action_type, action_name, *, node_name: str = "mock_server_node", **kwargs):
        node = make_node(node_name)
        server = MockActionServer(node, action_type, action_name, **kwargs)
        created.append(server)
        return server

    yield _factory

    for server in created:
        server.destroy()


@pytest.fixture
def make_test_client_on_node(make_node):
    """
    Factory fixture for TestActionClient that creates a dedicated node per client.

    Use this instead of make_test_client when clients must be isolated on
    separate nodes.  All clients and their nodes are destroyed at end of test.

    Usage::

        def test_something(make_test_client_on_node):
            client = make_test_client_on_node(MyAction, '/my_action', node_name='my_node')
    """
    created = []

    def _factory(
        action_type,
        action_name,
        *,
        node_name: str = "test_client_node",
        timeout: float = _WAIT_FOR_SERVER_TIMEOUT,
    ):
        node = make_node(node_name)
        client = TestActionClient(node, action_type, action_name)
        created.append(client)
        assert client.wait_for_server(timeout=timeout), (
            f"Action server '{action_name}' did not become available within {timeout}s"
        )
        return client

    yield _factory

    for client in created:
        client.destroy()
