from mypy import api

imports = ""
imports += "import ophyd;"
imports += "from ophyd import flyers, sim;"
imports += "hw = sim.hw();"


def run(cmd):
    normal_report, error_report, exit_status = api.run(
        ["--command", cmd, "--follow-imports=skip"]
    )
    print(cmd.split(";")[-1])
    print("  ", normal_report)
    print("  ", error_report)
    assert exit_status == 0


def test_checkable():
    cmd = imports + "from bluesky.protocols import Checkable;"
    run(cmd + "foo: Checkable = hw.motor1")
    run(cmd + "foo: Checkable = ophyd.Device(name='test')")


def test_flyable():
    cmd = imports + "from bluesky.protocols import Flyable;"
    run(cmd + "foo: Flyable = hw.flyer1")
    run(cmd + "foo: Flyable = sim.TrivialFlyer()")


def test_hinted():
    cmd = imports + "from bluesky.protocols import Hinted;"
    run(cmd + "foo: Hinted = ophyd.Signal(name='test')")


def test_movable():
    cmd = imports + "from bluesky.protocols import Movable;"
    run(cmd + "foo: Movable = hw.motor1")
    run(cmd + "foo: Movable = ophyd.Device(name='test')")
    run(cmd + "foo: Movable = hw.flyer1")


def test_pausable():
    cmd = imports + "from bluesky.protocols import Pausable;"
    run(cmd + "foo: Pausable = hw.motor1")
    run(cmd + "foo: Pausable = ophyd.Device(name='test')")


def test_readable():
    cmd = imports + "from bluesky.protocols import Readable;"
    run(cmd + "foo: Readable = hw.motor1")
    run(cmd + "foo: Readable = ophyd.Device(name='test')")
    run(cmd + "foo: Readable = hw.signal1")


def test_stageable():
    cmd = imports + "from bluesky.protocols import Stageable;"
    run(cmd + "foo: Stageable = hw.motor1")
    run(cmd + "foo: Stageable = ophyd.Device(name='test')")


def test_status():
    cmd = imports + "from bluesky.protocols import Status;"
    run(cmd + "foo: Status = ophyd.status.Status()")
    run(cmd + "foo: Status = ophyd.status.StatusBase()")


def test_stoppable():
    cmd = imports + "from bluesky.protocols import Stoppable;"
    run(cmd + "foo: Stoppable = hw.motor1")
    run(cmd + "foo: Stoppable = hw.flyer1")


def test_subscribable():
    cmd = imports + "from bluesky.protocols import Subscribable;"
    run(cmd + "foo: Subscribable = hw.signal1")
    run(cmd + "foo: Subscribable = ophyd.Signal(name='test')")
    run(cmd + "foo: Subscribable = ophyd.Device(name='test')")
    run(cmd + "foo: Subscribable = hw.motor1")
    run(cmd + "foo: Subscribable = hw.flyer1")


if __name__ == "__main__":
    test_checkable()
    test_flyable()
    test_hinted()
    test_movable()
    test_pausable()
    test_readable()
    test_stageable()
    test_status()
    test_stoppable()
    test_subscribable()
