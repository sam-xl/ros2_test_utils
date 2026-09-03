import os  # noqa: D100
import sys

from sphinx import addnodes


def _strip_fixture_module_prefix(app, doctree):
    for node in doctree.traverse(addnodes.desc):
        if node.get("domain") != "py" or node.get("objtype") != "function":
            continue
        for sig in node.traverse(addnodes.desc_signature):
            if sig.get("module") == "ros2_test_utils.fixtures":
                for addname in sig.traverse(addnodes.desc_addname):
                    addname.parent.remove(addname)


def setup(app):  # noqa: D103
    app.connect("doctree-read", _strip_fixture_module_prefix)


sys.path.insert(0, os.path.abspath("../ros2_test_utils"))

project = "ros2_test_utils"
author = "D. Kroezen"
release = "0.0.1"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

html_theme = "furo"
autodoc_member_order = "bysource"
autodoc_mock_imports = ["rclpy", "action_msgs"]
