import subprocess
import tempfile
from typing import Callable, List, Literal

import pytest
from mypy import api

imports = ""
imports += "import ophyd;"
imports += "from ophyd import flyers, sim;"
imports += "hw = sim.hw();"

SupportedTypeCheckers = Literal["pyright", "mypy"]
enabled_type_checkers: List[SupportedTypeCheckers] = ["pyright", "mypy"]


@pytest.fixture(params=enabled_type_checkers, scope="session")
def run(request) -> Callable[[str], None]:
    def run_mypy_command(cmd):
        normal_report, error_report, exit_status = api.run(
            [
                "--command",
                cmd,
                # Can help with mypy performance issues
                "--cache-fine-grained",
                # We need to follow imports to typecheck properly,
                # but there are still a some type issues in some of Ophyd's modules.
                # This will ignore those error silently so that these checks can complete
                "--follow-imports=silent",
                # If an imported module is not found, throw an error instead of silently converting types to Any
                "--disallow-any-unimported",
            ]
        )
        print(cmd.split(";")[-1])
        print("  ", normal_report)
        print("  ", error_report)
        assert exit_status == 0

    def run_pyright_command(cmd):
        with tempfile.NamedTemporaryFile(suffix=".py") as fp:
            print(f"Writing program to temporary file: '{fp.name}'...")
            fp.write(cmd.encode("utf-8"))
            fp.flush()
            command = ["pyright", fp.name]
            print(f"Running: '{command}'...")
            result = subprocess.run(command, capture_output=True, text=True)
            print(cmd.split(";")[-1])
            print("  ", result.stdout)
            print("  ", result.stderr)
            assert result.returncode == 0, result.stdout

    tool_name: SupportedTypeCheckers = request.param
    if tool_name == "mypy":
        return run_mypy_command
    elif tool_name == "pyright":
        return run_pyright_command
    else:
        raise Exception(f"Unsupported type checking tool: '{tool_name}'")


@pytest.mark.timeout(60)
def test_configurable(run):
    cmd = imports + "from bluesky.protocols import Configurable;"
    run(cmd + "foo: Configurable = hw.motor1")
    run(cmd + "foo: Configurable = ophyd.Device(name='test')")
    run(cmd + "foo: Configurable = hw.signal")


def test_triggerable(run):
    cmd = imports + "from bluesky.protocols import Triggerable;"
    run(cmd + "foo: Triggerable = hw.det")


def test_checkable(run):
    cmd = imports + "from bluesky.protocols import Checkable;"
    run(cmd + "foo: Checkable = hw.motor1")
    run(cmd + "foo: Checkable = ophyd.Device(name='test')")


def test_hashints(run):
    cmd = imports + "from bluesky.protocols import HasHints;"
    run(cmd + "foo: HasHints = ophyd.Signal(name='test')")


def test_flyable(run):
    cmd = imports + "from bluesky.protocols import Flyable;"
    run(cmd + "foo: Flyable = hw.flyer1")
    run(cmd + "foo: Flyable = sim.TrivialFlyer()")


@pytest.mark.timeout(60)
def test_movable(run):
    cmd = imports + "from bluesky.protocols import Movable;"
    run(cmd + "foo: Movable = hw.motor1")
    run(cmd + "foo: Movable = hw.flyer1")
    run(cmd + "foo: Movable = ophyd.Component(ophyd.Signal, 'prefix')")
    run(cmd + "foo: Movable = ophyd.Device(name='test')")


def test_pausable(run):
    cmd = imports + "from bluesky.protocols import Pausable;"
    run(cmd + "foo: Pausable = hw.motor1")
    run(cmd + "foo: Pausable = ophyd.Device(name='test')")


def test_readable(run):
    cmd = imports + "from bluesky.protocols import Readable;"
    run(cmd + "foo: Readable = hw.motor1")
    run(cmd + "foo: Readable = ophyd.Device(name='test')")
    run(cmd + "foo: Readable = hw.signal")


def test_stageable(run):
    cmd = imports + "from bluesky.protocols import Stageable;"
    run(cmd + "foo: Stageable = hw.motor1")
    run(cmd + "foo: Stageable = ophyd.Device(name='test')")


def test_status(run):
    cmd = imports + "from bluesky.protocols import Status;"
    run(cmd + "foo: Status = ophyd.status.Status()")
    run(cmd + "foo: Status = ophyd.status.StatusBase()")


def test_stoppable(run):
    cmd = imports + "from bluesky.protocols import Stoppable;"
    run(cmd + "foo: Stoppable = hw.motor1")
    run(cmd + "foo: Stoppable = hw.flyer1")


# TODO: Ophyd signature is incompatible with bluesky protocol
# (extra parameters, returns int instead of None, different parameter names)
# Pyright is stricter and picks this up. Disabled for now
@pytest.mark.skip()
def test_subscribable(run):
    cmd = imports + "from bluesky.protocols import Subscribable;"
    run(cmd + "foo: Subscribable = hw.signal")
    run(cmd + "foo: Subscribable = ophyd.Signal(name='test')")
    run(cmd + "foo: Subscribable = ophyd.Device(name='test')")
    run(cmd + "foo: Subscribable = hw.motor1")
    run(cmd + "foo: Subscribable = hw.flyer1")


if __name__ == "__main__":
    test_configurable()
    test_triggerable()
    test_checkable()
    test_hashints()
    test_flyable()
    test_movable()
    test_pausable()
    test_readable()
    test_stageable()
    test_status()
    test_stoppable()
    # test_subscribable() # Disabled temporarily, see test
