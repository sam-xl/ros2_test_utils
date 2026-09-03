# ros2_test_utils

## Overview

This package provides a pytest plugin and test helper classes for integration tests of ROS 2 interfaces. Currently this covers actions, but services and topics are planned.

**Maintainer:** D. Kroezen (GitHub username: dave992)

Requires Python 3.10+, ROS2 Humble or later.

## Installation

### Build from source

To build from source, clone the latest version from this repository into your workspace:

```bash
git clone https://github.com/sam-xl/ros2_test_utils.git
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

Once built or installed, the test helper classes and pytest fixtures are available in your package's tests.

## Detailed Documentation

For the full API reference — outcomes, configuration, cancellation, async goals, inspection properties, and pytest fixtures — see [docs/index.rst](docs/index.rst).

### Building the docs locally

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install sphinx furo pytest

rm -rf docs/_build
.venv-docs/bin/sphinx-build -W --keep-going -b html docs/ docs/_build/html
```

Open `docs/_build/html/index.html` in a browser to view the result.

This mirrors the [docs CI workflow](.github/workflows/docs.yml).

## Bugs & Feature Requests

Please report bugs and request features using the [Issue Tracker](https://github.com/sam-xl/ros2_test_utils/issues).
