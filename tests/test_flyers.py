import time
import pytest

from ophyd import (Component as Cpt,
                   SimDetector, SimDetectorCam, StatsPlugin, EpicsSignal)
from ophyd.areadetector.base import EpicsSignalWithRBV
from ophyd.flyers import (AreaDetectorTimeseriesCollector,
                          WaveformCollector)
from ophyd.status import wait


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

    det = Detector(prefix, name='sim')
    try:
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
    print('tscollector repr', repr(tscollector))
    print('simdet stage sigs', sim_detector.stage_sigs)
    print('tscoll stage sigs', tscollector.stage_sigs)
    print('cam stage sigs', cam.stage_sigs)
    print('stats stage sigs', sim_detector.stats.stage_sigs)

    tscollector.stop()
    tscollector.stage_sigs[tscollector.num_points] = num_points

    sim_detector.stage()
    tscollector.kickoff()

    for i in range(num_points):
        st = sim_detector.trigger()
        wait(st)
        print(st)
        time.sleep(0.1)

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

    det = Detector(prefix)
    try:
        det.wait_for_connection(timeout=1.0)
    except TimeoutError:
        pytest.skip('IOC unavailable')
    return det


@pytest.fixture
def wfcol(wf_sim_detector):
    return wf_sim_detector.wfcol


def test_waveform(wf_sim_detector, wfcol):
    print('waveform collector', wfcol)
