"""The scheduler unit tests do not depend on the py-fsrs oracle being installed."""
import os


# --- The scheduler unit tests do not depend on the oracle -----------------------------------------

def test_fsrs_unit_tests_do_not_depend_on_the_oracle():
    """A module-level skip once hid every scheduler test when py-fsrs was absent."""
    with open(os.path.join(os.path.dirname(__file__), "test_fsrs.py")) as fh:
        src = fh.read()
    assert "import fsrs as py_fsrs" not in src and "allow_module_level" not in src
