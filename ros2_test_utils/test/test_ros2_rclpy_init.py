"""
Tests for the ros2_rclpy_init session fixture guards.

Each guard is tested in isolation:
- Pre-init: fixture raises if rclpy is already initialized when it runs.
- Init during session: rclpy.init() raises while the fixture owns the session.
- Shutdown during session: rclpy.shutdown() raises while the fixture owns the session.

The pre-init guard is tested by calling the fixture function directly as a
generator (bypassing pytest's session machinery) and patching rclpy.ok so no
real ROS state is modified.
"""

from unittest.mock import patch

import pytest
import rclpy

from ros2_test_utils.fixtures import _ros2_rclpy_init_impl


def test_pre_init_guard():
    """Fixture raises if rclpy is already initialized before it runs."""
    with patch.object(rclpy, "ok", return_value=True):
        gen = _ros2_rclpy_init_impl()
        with pytest.raises(RuntimeError, match="already initialized"):
            next(gen)


def test_init_raises_during_session(ros2_rclpy_init):  # noqa: ARG001
    """rclpy.init() raises while the fixture owns the session."""
    with pytest.raises(RuntimeError, match="rclpy.init\\(\\) was called"):
        rclpy.init()


def test_shutdown_raises_during_session(ros2_rclpy_init):  # noqa: ARG001
    """rclpy.shutdown() raises while the fixture owns the session."""
    with pytest.raises(RuntimeError, match="rclpy.shutdown\\(\\) was called"):
        rclpy.shutdown()
