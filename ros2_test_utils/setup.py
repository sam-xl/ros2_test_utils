from setuptools import setup

package_name = "ros2_test_utils"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name, f"{package_name}.action"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Dave Kroezen",
    maintainer_email="d.kroezen@tudelft.nl",
    description="pytest plugin and test helper classes for integration tests of ROS 2 interfaces.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [],
        "pytest11": [
            "ros2_test_utils = ros2_test_utils.fixtures",
        ],
    },
)
