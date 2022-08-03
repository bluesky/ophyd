"""
Issue 944:  TypeError: No conversion path for dtype: dtype('<U1').

Since the tests include different configurations of
EpicsSignalBase.set_defaults(), and that code must be called
before creating any instance of EpicsSignalBase (or subclasses),
most tests need to be run as a separate process.

Needs this set in the top-most conftest.py file to enable 'testdir':

    echo "pytest_plugins = 'pytester'" >> conftest.py
"""

from .config import motor_recs

pv_base = motor_recs[0]


def run_test_code(testdir, code):
    testdir.makepyfile(code)
    result = testdir.runpytest_subprocess()
    result.stdout.fnmatch_lines(["* 1 passed in *"])


def test_local_without_defaults_no_string(testdir):
    from ophyd import EpicsSignal

    signal = EpicsSignal(f"{pv_base}.SCAN", name="signal")
    signal.wait_for_connection()
    desc = signal.describe()
    assert not signal.as_string
    assert desc["signal"]["dtype"] == "integer"


def test_without_defaults_no_string(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal

    pv_base = "%s"

    def test_without_defaults_no_string():
        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal")
        signal.wait_for_connection()
        desc = signal.describe()
        assert not signal.as_string
        assert desc["signal"]["dtype"] == "integer"
    """
        % pv_base,
    )


def test_without_defaults_as_string(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal

    pv_base = "%s"

    def test_without_defaults_no_string():
        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal", string=True)
        signal.wait_for_connection()
        desc = signal.describe()
        assert signal.as_string
        assert desc["signal"]["dtype"] == "string"
    """
        % pv_base,
    )


def test_with_all_defaults_no_string(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal
    from ophyd.signal import EpicsSignalBase

    pv_base = "%s"

    def test_without_defaults_no_string():
        EpicsSignalBase.set_defaults(
            auto_monitor=True,
            connection_timeout=1,
            timeout=60,
            write_timeout=60,
        )
        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal")
        signal.wait_for_connection()
        desc = signal.describe()
        assert not signal.as_string
        assert desc["signal"]["dtype"] == "integer"
    """
        % pv_base,
    )


def test_with_all_defaults_as_string(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal
    from ophyd.signal import EpicsSignalBase

    pv_base = "%s"

    def test_without_defaults_no_string():
        EpicsSignalBase.set_defaults(
            auto_monitor=True,
            connection_timeout=1,
            timeout=60,
            write_timeout=60,
        )

        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal", string=True)
        signal.wait_for_connection()
        desc = signal.describe()
        assert signal.as_string
        assert desc["signal"]["dtype"] == "string"
    """
        % pv_base,
    )


def test_with_all_defaults_auto_monitor(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal
    from ophyd.signal import EpicsSignalBase

    pv_base = "%s"

    def test_without_defaults_no_string():
        EpicsSignalBase.set_defaults(
            auto_monitor=True,
        )

        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal", string=True)
        signal.wait_for_connection()
        desc = signal.describe()
        assert signal.as_string
        assert desc["signal"]["dtype"] == "string"
    """
        % pv_base,
    )


def test_with_all_defaults_connection_timeout(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal
    from ophyd.signal import EpicsSignalBase

    pv_base = "%s"

    def test_without_defaults_no_string():
        EpicsSignalBase.set_defaults(
            connection_timeout=1,
        )

        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal", string=True)
        signal.wait_for_connection()
        desc = signal.describe()
        assert signal.as_string
        assert desc["signal"]["dtype"] == "string"
    """
        % pv_base,
    )


def test_with_all_defaults_timeout(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal
    from ophyd.signal import EpicsSignalBase

    pv_base = "%s"

    def test_without_defaults_no_string():
        EpicsSignalBase.set_defaults(
            timeout=60,
        )

        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal", string=True)
        signal.wait_for_connection()
        desc = signal.describe()
        assert signal.as_string
        assert desc["signal"]["dtype"] == "string"
    """
        % pv_base,
    )


def test_with_all_defaults_write_timeout(testdir):
    run_test_code(
        testdir,
        """
    from ophyd import EpicsSignal
    from ophyd.signal import EpicsSignalBase

    pv_base = "%s"

    def test_without_defaults_no_string():
        EpicsSignalBase.set_defaults(
            write_timeout=60,
        )

        signal = EpicsSignal(f"{pv_base}.SCAN", name="signal", string=True)
        signal.wait_for_connection()
        desc = signal.describe()
        assert signal.as_string
        assert desc["signal"]["dtype"] == "string"
    """
        % pv_base,
    )
