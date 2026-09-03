Examples
========

Below some minimal examples are shown for the ``conftest.py`` and ``test_*.py`` file for the supported interfaces and helper classes.

As shown, it is recommended to use the provided ``pytest`` fixtures to create your mock server or test client. By default these are created as part of a single ``test_node``. Alternatively, there are also fixtures available that let you specify the node yourself, so you have more control over the ``rclpy`` initialization / shutdown, and the executor that is used.

Actions
-------

Testing of an Action server
~~~~~~~~~~~~~~~~~~~~~~~~~~~

When testing an action server, you can make use of the :class:`~ros2_test_utils.TestActionClient` via the :func:`~ros2_test_utils.fixtures.make_test_client` fixture.

In your ``conftest.py`` define your fixtures and launch descriptions that are used in the tests.

.. code-block:: python

   # your_package/test/conftest.py
   import pytest
   from example_interfaces.action import Fibonacci

   # ... use launch_pytest to load your launch_description if needed ...

   @pytest.fixture
   def fibonacci_client(launch_description, make_test_client):
       # launch_description ensures the server is up before wait_for_server runs
       return make_test_client(Fibonacci, '/fibonacci')

And the tests themselves:

.. code-block:: python

   # your_package/test/test_fibonacci_server.py
   import pytest
   from action_msgs.msg import GoalStatus

   @pytest.mark.launch(fixture=launch_description)
   def test_fibonacci_server(fibonacci_client):
       response = fibonacci_client.send_goal(Fibonacci.Goal(order=5))

       assert response.status == GoalStatus.STATUS_SUCCEEDED
       assert response.result == Fibonacci.Result(...)

   # ... more tests ...

Testing of an Action client
~~~~~~~~~~~~~~~~~~~~~~~~~~~

When testing an action client, use the :class:`~ros2_test_utils.MockActionServer` via the :func:`~ros2_test_utils.fixtures.make_mock_server` fixture to stand in for the real server.

.. code-block:: python

   # your_package/test/conftest.py
   import pytest
   from example_interfaces.action import Fibonacci

   # ... use launch_pytest to load your launch_description if needed ...

   @pytest.fixture
   def fibonacci_server(make_mock_server):
       return make_mock_server(Fibonacci, '/fibonacci')

And the tests themselves:

.. code-block:: python

   # your_package/test/test_fibonacci_client.py
   def test_fibonacci_client(fibonacci_server):
       fibonacci_server.set_outcome(...)
       fibonacci_server.set_feedback(...)
       fibonacci_server.set_result(...)

       # ... configure and trigger your client under test ...

       assert fibonacci_server.goal_count == 1
       assert fibonacci_server.last_goal_request == ...

   # ... more tests ...
