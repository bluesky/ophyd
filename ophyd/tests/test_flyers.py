import time
import pytest

from ophyd import (Component as Cpt,
                   SimDetector, SimDetectorCam, StatsPlugin, EpicsMotor,
                   Device)
from ophyd.areadetector.base import EpicsSignalWithRBV
from ophyd.flyers import (AreaDetectorTimeseriesCollector,
                          WaveformCollector,
                          MonitorFlyerMixin)
from ophyd.status import wait
from ophyd.utils import OrderedDefaultDict


@pytest.fixture
def prefix():
    return 'XF:23ID1-ES{Tst-Cam:1}'


@pytest.fixture(params=['Stats1:',
                        # 'Stats2:',
                        # 'Stats3:',
                        # 'Stats4:',
                        # 'Stats5:',
                        ]
                )
def stats_suffix(request):
    return request.param


@pytest.fixture(scope='function')
def ts_sim_detector(prefix, stats_suffix):
    class Detector(SimDetector):
        acquire = Cpt(EpicsSignalWithRBV, 'cam1:Acquire', trigger_value=1)
        cam = Cpt(SimDetectorCam, 'cam1:')
        ts_col = Cpt(AreaDetectorTimeseriesCollector, stats_suffix)
        stats = Cpt(StatsPlugin, stats_suffix)

    try:
        det = Detector(prefix, name='sim')
        det.wait_for_connection(timeout=1.0)
    except TimeoutError:
        pytest.skip('IOC unavailable')
    return det


@pytest.fixture
def tscollector(ts_sim_detector):
    return ts_sim_detector.ts_col


def test_ad_time_series(ts_sim_detector, tscollector):
    sim_detector = ts_sim_detector

    num_points = 3

    cam = sim_detector.cam
    cam.stage_sigs[cam.acquire_time] = 0.001
    cam.stage_sigs[cam.acquire_period] = 0.001
    cam.stage_sigs[cam.image_mode] = 'Single'
    cam.stage_sigs[cam.trigger_mode] = 'Internal'

    print('tscollector desc', tscollector.describe())
    print('tscollector flyer desc', tscollector.describe_collect())
    print('tscollector repr', repr(tscollector))
    print('simdet stage sigs', sim_detector.stage_sigs)
    print('tscoll stage sigs', tscollector.stage_sigs)
    print('cam stage sigs', cam.stage_sigs)
    print('stats stage sigs', sim_detector.stats.stage_sigs)

    st = tscollector.complete()
    wait(st)

    tscollector.stage_sigs[tscollector.num_points] = num_points

    sim_detector.stage()
    tscollector.kickoff()

    for i in range(num_points):
        st = sim_detector.trigger()
        wait(st)
        print(st)
        time.sleep(0.1)

    tscollector.pause()
    tscollector.resume()

    collected = list(tscollector.collect())
    print('collected', collected)
    sim_detector.unstage()
    assert len(collected) == num_points
    # TODO any more validation here?


@pytest.fixture(scope='function')
def wf_sim_detector(prefix):
    suffix = '??TODO??'

    class Detector(SimDetector):
        wfcol = Cpt(WaveformCollector, suffix)

    try:
        det = Detector(prefix, name='det')
        det.wait_for_connection(timeout=1.0)
    except TimeoutError:
        pytest.skip('IOC unavailable')
    return det


@pytest.fixture
def wfcol(wf_sim_detector):
    return wf_sim_detector.wfcol


def test_waveform(wf_sim_detector, wfcol):
    print('waveform collector', wfcol)
    print('wfcol flyer desc', wfcol.describe_collect())


@pytest.mark.parametrize('pivot', [True, False])
def test_monitor_flyer(pivot):
    class BasicDevice(Device):
        mtr1 = Cpt(EpicsMotor, 'XF:31IDA-OP{Tbl-Ax:X2}Mtr')
        mtr2 = Cpt(EpicsMotor, 'XF:31IDA-OP{Tbl-Ax:X3}Mtr')

    class FlyerDevice(MonitorFlyerMixin, BasicDevice):
        pass

    fdev = FlyerDevice('', name='fdev', stream_names={'mtr1.user_readback': 'oranges'},
                       pivot=pivot)
    fdev.wait_for_connection()

    fdev.monitor_attrs = ['mtr1.user_readback', 'mtr2.user_readback']
    fdev.describe()

    st = fdev.kickoff()
    wait(st)

    mtr1, mtr2 = fdev.mtr1, fdev.mtr2
    rbv1, rbv2 = mtr1.position, mtr2.position
    fdev.mtr1.move(rbv1 + 0.2, wait=True)
    fdev.mtr2.move(rbv2 + 0.2, wait=True)

    fdev.pause()

    fdev.mtr1.move(rbv1 - 0.2, wait=True)
    fdev.mtr2.move(rbv2 - 0.2, wait=True)

    fdev.resume()
    st = fdev.complete()
    wait(st)

    print(fdev.describe_collect())

    desc1 = fdev.mtr1.user_readback.describe()
    desc2 = fdev.mtr2.user_readback.describe()

    if not pivot:
        desc1[fdev.mtr1.user_readback.name]['dtype'] = 'array'
        desc2[fdev.mtr2.user_readback.name]['dtype'] = 'array'

    assert (fdev.describe_collect() ==
            {'oranges': desc1,
             'fdev_mtr2': desc2,
             }
            )
    data = list(fdev.collect())
    print('collected data', data)
    # data from both motors

    if not pivot:
        assert len(data) == 2
        d1 = data[0]['data']['fdev_mtr1']
        d2 = data[1]['data']['fdev_mtr2']

    else:
        assert len(data) >= 2

        d1 = [d['data']['fdev_mtr1'] for d in data
              if 'fdev_mtr1' in d['data']]
        d2 = [d['data']['fdev_mtr2'] for d in data
              if 'fdev_mtr2' in d['data']]

    # and at least more than one data point...
    assert len(d1) > 1
    assert len(d2) > 1

    print('data1', d1)
    print('data2', d2)
    # raise ValueError()
