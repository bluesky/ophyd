import logging
import time
from copy import copy
from types import SimpleNamespace

import pytest
from caproto.tests.conftest import run_example_ioc

from ophyd.scaler import EpicsScaler, ScalerCH
from ophyd.utils import enum

from .test_utils import assert_OD_equal_ignore_ts

ScalerMode = enum(ONE_SHOT=0, AUTO_COUNT=1)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def scaler_test_ioc(prefix, request):
    name = "test_signal IOC"
    pvs = dict(scaler_prefix=f"{prefix}")

    process = run_example_ioc(
        "ophyd.tests.scaler_ioc",
        request=request,
        pv_to_check=pvs["scaler_prefix"] + ".CNT",
        args=("--prefix", prefix, "-v"),
    )
    return SimpleNamespace(
        process=process, prefix=prefix, name=name, pvs=pvs, type="caproto"
    )


@pytest.fixture(scope="function")
def scaler(cleanup, scaler_test_ioc):
    scaler = EpicsScaler(scaler_test_ioc.pvs["scaler_prefix"], name="scaler")
    scaler.wait_for_connection()
    cleanup.add(scaler)
    return scaler


@pytest.fixture(scope="function")
def scaler_ch(cleanup, scaler_test_ioc):
    ch = ScalerCH(scaler_test_ioc.pvs["scaler_prefix"])
    ch.wait_for_connection()
    cleanup.add(scaler)
    return ch


def test_scaler_connects(scaler):
    ...


def test_scaler_functionality(scaler):
    scaler.read_attrs = ["channels"]

    scaler.wait_for_connection()
    scaler.count_mode.put("OneShot")
    scaler.preset_time.put(5.2)

    logger.info("Counting in One-Shot mode for %f s...", scaler.preset_time.get())
    scaler.count.put(1)
    logger.info("Sleeping...")
    time.sleep(0.1)
    logger.info("Done sleeping. Stopping counter...")
    scaler.stop()

    logger.info("Set mode to AutoCount")
    scaler.count_mode.put("AutoCount")
    scaler.count.put(1)
    logger.info('Begin auto-counting (aka "background counting")...')
    time.sleep(0.1)
    logger.info("Set mode to OneShot")
    scaler.count_mode.put("OneShot")
    time.sleep(0.1)
    logger.info("Stopping (aborting) auto-counting.")
    scaler.stop()

    logger.info("read() all channels in one-shot mode...")
    vals = scaler.read()
    logger.info(vals)
    assert "scaler_channels_chan1" in vals

    scaler.report
    scaler.read()

    assert copy(scaler).prefix == scaler.prefix
    assert copy(scaler).read_attrs == scaler.read_attrs
    assert copy(scaler).configuration_attrs == scaler.configuration_attrs
    repr(scaler)
    str(scaler)

    scaler.stage()
    old, new = scaler.configure({})
    scaler.unstage()

    assert_OD_equal_ignore_ts(old, new)

    scaler.stage()
    old_preset_time = scaler.preset_time.get()
    old, new = scaler.configure({"preset_time": 7})
    scaler.unstage()

    assert old.pop("scaler_preset_time")["value"] == old_preset_time
    assert new.pop("scaler_preset_time")["value"] == 7
    assert_OD_equal_ignore_ts(old, new)

    scaler.hints == {"fields": [scaler.channels.name]}


def test_signal_separate(scaler):
    scaler.read_attrs = ["channels.chan1"]

    data = scaler.read()
    assert "scaler_channels_chan1" in data
    assert "scaler_channels_chan2" not in data


def smoke_test_scalerCH(scaler_ch):
    data = scaler_ch.read()
    assert "scaler_channels_chan1" in data
    assert "scaler_channels_chan2" not in data
