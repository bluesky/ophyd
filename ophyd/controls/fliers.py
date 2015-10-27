import time as ttime

from epics import PV

from .ophydobj import StatusBase


class AreaDetectorTimeseriesCollector:
    def __init__(self, name, pv_basename, num_points=1000000):
        self._name = name
        self._pv_basename = pv_basename
        self.num_points = num_points

        self._pv_tscontrol = PV("{}TSControl".format(pv_basename))
        self._pv_num_points = PV("{}TSNumPoints".format(pv_basename))
        self._pv_cur_point = PV("{}TSCurrentPoint".format(pv_basename))
        self._pv_wfrm = PV("{}TSTotal".format(pv_basename),
                           auto_monitor=False)
        self._pv_wfrm_ts = PV("{}TSTimestamp".format(pv_basename),
                              auto_monitor=False)

    def _get_wfrms(self):
        n = self._pv_cur_point.get()
        if n:
            return (self._pv_wfrm.get(count=n),
                    self._pv_wfrm_ts.get(count=n))
        else:
            return ([], [])

    def kickoff(self):
        self._pv_num_points.put(self.num_points, wait=True)
        # Erase buffer and start collection
        self._pv_tscontrol.put(0, wait=True)
        # make status object
        status = StatusBase()
        # it always done, the scan should never even try to wait for this
        status._finished()
        return status

    def collect(self):
        self.stop()
        payload_val, payload_time = self._get_wfrm()
        for v, t in zip(payload_val, payload_time):
            yield {'data': {self._name: v},
                   'timestamps': {self._name: t},
                   'time': ttime.time()}


    def stop(self):
        self._pv_tscontrol.put(2, wait=True)  # Stop Collection

    def describe(self):
        return [{self._name: {'source': self._pv_basename,
                              'dtype': 'number',
                              'shape': None}}, ]


class WaveformCollector:
    def __init__(self, name, pv_basename, data_is_time=True):
        self._name = name
        self._pv_basename = pv_basename
        self._pv_sel = PV("{}Sw-Sel".format(pv_basename))
        self._pv_rst = PV("{}Rst-Sel".format(pv_basename))
        self._pv_wfrm_n = PV("{}Val:TimeN-I".format(pv_basename),
                             auto_monitor=False)
        self._pv_wfrm = PV("{}Val:Time-Wfrm".format(pv_basename),
                           auto_monitor=False)
        self._pv_wfrm_nord = PV("{}Val:Time-Wfrm.NORD".format(pv_basename),
                                auto_monitor=False)
        self._data_is_time = data_is_time

    def _get_wfrm(self):
        if self._pv_wfrm_n.get():
            return self._pv_wfrm.get(count=int(self._pv_wfrm_nord.get()))
        else:
            return []

    def kickoff(self):
        # Put us in reset mode
        self._pv_sel.put(2, wait=True)
        # Trigger processing
        self._pv_rst.put(1, wait=True)
        # Start Buffer
        self._pv_sel.put(1, wait=True)
        # make status object
        status = StatusBase()
        # it always done, the scan should never even try to wait for this
        status._finished()
        return status

    def collect(self):
        self.stop()
        payload = self._get_wfrm()
        if len(payload) == 0:
            return
        for i, v in enumerate(payload):
            x = v if self._data_is_time else i
            ev = {'data': {self._name: x},
                  'timestamps': {self._name: v},
                  'time': v}
            yield ev

    def stop(self):
        self._pv_sel.put(0, wait=True)  # Stop Collection

    def describe(self):
        return [{self._name: {'source': self._pv_basename,
                              'dtype': 'number',
                              'shape': None}}, ]
