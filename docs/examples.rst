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

Topics
------

Testing of a publisher
~~~~~~~~~~~~~~~~~~~~~~

When testing a node that publishes, use the :class:`~ros2_test_utils.TestSubscriber` via the :func:`~ros2_test_utils.fixtures.make_test_subscriber` fixture. It waits for the node's publisher, then collects every message.

.. code-block:: python

   # your_package/test/test_talker.py
   from example_interfaces.msg import String

   @pytest.mark.launch(fixture=launch_description)
   def test_talker(make_test_subscriber):
       chatter = make_test_subscriber(String, '/chatter')

       message = chatter.wait_for_message(lambda m: m.data.startswith('hello'))

       assert chatter.message_count >= 1

Messages received before :meth:`~ros2_test_utils.TestSubscriber.wait_for_message` is called count too, so a message is not missed when it arrives early.

The same helper reads a node's log messages from ``/rosout``. Its publisher is transient local, so a subscription with that durability also receives what the node logged before the test subscribed:

.. code-block:: python

   from rcl_interfaces.msg import Log
   from rclpy.qos import DurabilityPolicy, QoSProfile

   def test_talker_warns(make_test_subscriber):
       rosout_qos = QoSProfile(depth=100, durability=DurabilityPolicy.TRANSIENT_LOCAL)
       rosout = make_test_subscriber(Log, '/rosout', qos_profile=rosout_qos)

       rosout.wait_for_message(lambda log: log.name == 'talker' and 'warning' in log.msg)

Testing of a subscriber
~~~~~~~~~~~~~~~~~~~~~~~

When testing a node that subscribes, publish to it through the :func:`~ros2_test_utils.fixtures.make_test_publisher` fixture. It returns a plain ``rclpy`` publisher once the node's subscription has matched, so the first message is not lost. That message can still arrive late, if the node's subscription discovers the publisher only afterwards; ``wait_for_all_acked()`` waits until the node has received it.

.. code-block:: python

   # your_package/test/test_listener.py
   from example_interfaces.msg import String
   from rclpy.duration import Duration

   @pytest.mark.launch(fixture=launch_description)
   def test_listener(make_test_publisher, make_test_subscriber):
       chatter = make_test_publisher(String, '/chatter')
       echo = make_test_subscriber(String, '/echo')

       chatter.publish(String(data='hello'))
       assert chatter.wait_for_all_acked(Duration(seconds=5))

       assert echo.wait_for_message().data == 'hello'
