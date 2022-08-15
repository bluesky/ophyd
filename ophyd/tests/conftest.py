import logging
import uuid
from types import SimpleNamespace

import pytest

from ophyd import Component as Cpt
from ophyd import EpicsMotor, EpicsSignal, EpicsSignalRO, Signal, set_cl
from ophyd.utils.epics_pvs import AlarmSeverity, AlarmStatus

logger = logging.getLogger(__name__)


@pytest.fixture()
def hw(tmpdir):
    from ophyd.sim import hw

    return hw(str(tmpdir))


@pytest.fixture(params=["caproto", "pyepics"], autouse=True, scope="session")
def cl_selector(request):
    cl_name = request.param
    if cl_name == "caproto":
        pytest.importorskip("caproto")
        logging.getLogger("caproto.bcast").setLevel("INFO")
    elif cl_name == "pyepics":
        pytest.importorskip("epics")
    set_cl(cl_name)
    yield
    set_cl()


class CustomAlarmEpicsSignalRO(EpicsSignalRO):
    alarm_status = AlarmStatus.NO_ALARM
    alarm_severity = AlarmSeverity.NO_ALARM


class TestEpicsMotor(EpicsMotor):
    user_readback = Cpt(CustomAlarmEpicsSignalRO, ".RBV", kind="hinted")
    high_limit_switch = Cpt(Signal, value=0, kind="omitted")
    low_limit_switch = Cpt(Signal, value=0, kind="omitted")
    direction_of_travel = Cpt(Signal, value=0, kind="omitted")
    high_limit_value = Cpt(EpicsSignal, ".HLM", kind="config")
    low_limit_value = Cpt(EpicsSignal, ".LLM", kind="config")

    @user_readback.sub_value
    def _pos_changed(self, timestamp=None, value=None, **kwargs):
        """Callback from EPICS, indicating a change in position"""
        super()._pos_changed(timestamp=timestamp, value=value, **kwargs)


@pytest.fixture(scope="function")
def motor(request, cleanup):
    sim_pv = "XF:31IDA-OP{Tbl-Ax:X1}Mtr"

    motor = TestEpicsMotor(sim_pv, name="epicsmotor", settle_time=0.1, timeout=10.0)
    cleanup.add(motor)

    print("Created EpicsMotor:", motor)
    motor.wait_for_connection()
    motor.low_limit_value.put(-100, wait=True)
    motor.high_limit_value.put(100, wait=True)
    motor.set(0).wait()

    return motor


@pytest.fixture(scope="module")
def ad_prefix():
    "AreaDetector prefix"
    # prefixes = ['13SIM1:', 'XF:31IDA-BI{Cam:Tbl}']
    prefixes = ["ADSIM:"]

    for prefix in prefixes:
        test_pv = prefix + "TIFF1:PluginType_RBV"
        try:
            sig = EpicsSignalRO(test_pv)
            sig.wait_for_connection(timeout=2)
        except TimeoutError:
            ...
        else:
            print("areaDetector detected with prefix:", prefix)
            return prefix
        finally:
            sig.destroy()
    raise pytest.skip("No areaDetector IOC running")


@pytest.fixture(scope="function")
def prefix():
    "Random PV prefix for a server"
    return str(uuid.uuid4())[:8] + ":"


@pytest.fixture(scope="function")
def fake_motor_ioc(prefix, request):
    name = "Fake motor IOC"
    pvs = dict(
        setpoint=f"{prefix}setpoint",
        readback=f"{prefix}readback",
        moving=f"{prefix}moving",
        actuate=f"{prefix}actuate",
        stop=f"{prefix}stop",
        step_size=f"{prefix}step_size",
    )

    pytest.importorskip("caproto.tests.conftest")
    from caproto.tests.conftest import run_example_ioc

    process = run_example_ioc(
        "ophyd.tests.fake_motor_ioc",
        request=request,
        pv_to_check=pvs["setpoint"],
        args=("--prefix", prefix, "--list-pvs", "-v"),
    )
    return SimpleNamespace(
        process=process, prefix=prefix, name=name, pvs=pvs, type="caproto"
    )


@pytest.fixture(scope="function")
def signal_test_ioc(prefix, request):
    name = "test_signal IOC"
    pvs = dict(
        read_only=f"{prefix}read_only",
        read_write=f"{prefix}read_write",
        pair_set=f"{prefix}pair_set",
        pair_rbv=f"{prefix}pair_rbv",
        waveform=f"{prefix}waveform",
        bool_enum=f"{prefix}bool_enum",
        alarm_status=f"{prefix}alarm_status",
        set_severity=f"{prefix}set_severity",
        path=f"{prefix}path",
    )

    pytest.importorskip("caproto.tests.conftest")
    from caproto.tests.conftest import run_example_ioc

    process = run_example_ioc(
        "ophyd.tests.signal_ioc",
        request=request,
        pv_to_check=pvs["read_only"],
        args=("--prefix", prefix, "--list-pvs", "-v"),
    )
    return SimpleNamespace(
        process=process, prefix=prefix, name=name, pvs=pvs, type="caproto"
    )


@pytest.fixture(scope="function")
def cleanup(request):
    "Destroy all items added to the list during the finalizer"
    items = []

    class Cleaner:
        def add(self, item):
            items.append(item)

    def clean():
        for item in items:
            print("Destroying", item.name)
            item.destroy()
        items.clear()

    request.addfinalizer(clean)
    return Cleaner()
