import logging
import random
import sys
import threading
import time
import uuid
import weakref

import pytest
import numpy as np
import numpy.testing

from types import SimpleNamespace
from functools import wraps

from ophyd import (get_cl, set_cl, EpicsMotor, Signal, EpicsSignal,
                   EpicsSignalRO, Component as Cpt, MotorBundle)
from ophyd.utils.epics_pvs import (AlarmSeverity, AlarmStatus)
from caproto.tests.conftest import run_example_ioc

logger = logging.getLogger(__name__)


@pytest.fixture()
def hw():
    from ophyd.sim import hw
    return hw()


@pytest.fixture(params=['caproto', 'pyepics'], autouse=True)
def cl_selector(request):
    cl_name = request.param
    if cl_name == 'caproto':
        pytest.importorskip('caproto')
    elif cl_name == 'pyepics':
        pytest.importorskip('epics')
    set_cl(cl_name)
    yield
    set_cl()


class CustomAlarmEpicsSignalRO(EpicsSignalRO):
    alarm_status = AlarmStatus.NO_ALARM
    alarm_severity = AlarmSeverity.NO_ALARM


class TestEpicsMotor(EpicsMotor):
    user_readback = Cpt(CustomAlarmEpicsSignalRO, '.RBV', kind='hinted')
    high_limit_switch = Cpt(Signal, value=0, kind='omitted')
    low_limit_switch = Cpt(Signal, value=0, kind='omitted')
    direction_of_travel = Cpt(Signal, value=0, kind='omitted')
    high_limit_value = Cpt(EpicsSignal, '.HLM', kind='config')
    low_limit_value = Cpt(EpicsSignal, '.LLM', kind='config')

    @user_readback.sub_value
    def _pos_changed(self, timestamp=None, value=None, **kwargs):
        '''Callback from EPICS, indicating a change in position'''
        super()._pos_changed(timestamp=timestamp, value=value, **kwargs)


@pytest.fixture(scope='function')
def motor(request, cleanup):
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    motor = TestEpicsMotor(sim_pv, name='epicsmotor', settle_time=0.1,
                           timeout=10.0)
    cleanup.add(motor)

    print('Created EpicsMotor:', motor)
    motor.wait_for_connection()
    motor.low_limit_value.put(-100, wait=True)
    motor.high_limit_value.put(100, wait=True)

    while motor.motor_done_move.get() != 1:
        print('Waiting for {} to stop moving...'.format(motor))
        time.sleep(0.5)

    return motor


@pytest.fixture(scope='function')
def prefix():
    'Random PV prefix for a server'
    return str(uuid.uuid4())[:8] + ':'


@pytest.fixture(scope='function')
def fake_motor_ioc(prefix, request):
    name = 'Fake motor IOC'
    pvs = dict(setpoint=f'{prefix}setpoint',
               readback=f'{prefix}readback',
               moving=f'{prefix}moving',
               actuate=f'{prefix}actuate',
               stop=f'{prefix}stop',
               step_size=f'{prefix}step_size',
               )

    process = run_example_ioc('ophyd.tests.fake_motor_ioc',
                              request=request,
                              pv_to_check=pvs['setpoint'],
                              args=('--prefix', prefix, '--list-pvs'))
    return SimpleNamespace(process=process, prefix=prefix, name=name, pvs=pvs,
                           type='caproto')


@pytest.fixture(scope='function')
def signal_test_ioc(prefix, request):
    name = 'test_signal IOC'
    pvs = dict(read_only=f'{prefix}read_only',
               read_write=f'{prefix}read_write',
               waveform=f'{prefix}waveform',
               bool_enum=f'{prefix}bool_enum',
               )

    process = run_example_ioc('ophyd.tests.signal_ioc',
                              request=request,
                              pv_to_check=pvs['read_only'],
                              args=('--prefix', prefix, '--list-pvs'))
    return SimpleNamespace(process=process, prefix=prefix, name=name, pvs=pvs,
                           type='caproto')


@pytest.fixture(scope='function')
def cleanup(request):
    'Destroy all items added to the list during the finalizer'
    items = []

    class Cleaner:
        def add(self, item):
            items.append(item)

    def clean():
        for item in items:
            print('Destroying', item.name)
            item.destroy()
        items.clear()

    request.addfinalizer(clean)
    return Cleaner()
