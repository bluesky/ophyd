from __future__ import print_function
import logging

from collections import namedtuple

from .signal import (EpicsSignal, EpicsSignalRO)
from .device import OphydDevice
from .device import (Component as C, DynamicDeviceComponent as DDC)

logger = logging.getLogger(__name__)


_roi_field_map = {'name': (EpicsSignal, '.R{n}NM'),
                 'cnt': (EpicsSignalRO, '.R{n}'),
                 'net_cnt': (EpicsSignalRO, '.R{n}N'),
                 'preset_cnt': (EpicsSignal, '.R{n}P'),
                 'is_preset': (EpicsSignal, '.R{n}IP'),
                 'bkgnd_chans': (EpicsSignal, '.R{n}BG'),
                 'hi_chan': (EpicsSignal, '.R{n}HI'),
                 'lo_chan': (EpicsSignal, '.R{n}LO')
                }

_Roi = namedtuple('_Roi', _roi_field_map.keys())


class EpicsMCA(OphydDevice):
    '''SynApps MCA Record interface'''

    start = C(EpicsSignal, 'Start')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1)

    stop = C(EpicsSignal, '.STOP')
    preset_time = C(EpicsSignal, '.ERTM', write_pv='.PRTM')
    spectrum = C(EpicsSignalRO, '.VAL')
    background = C(EpicsSignalRO, '.BG')
    mode = C(EpicsSignal, '.MODE', string=True)

    def __init__(self, prefix, *, rois=None, read_attrs=None, 
                 configuration_attrs=None, monitor_attrs=None, name=None,
                 parent=None, **kwargs):
                
        if rois is not None:
            for roi in rois:
                # TODO - should this be method on the instance?
                # Permit ROI updates on a live object?
                kws = {k: v[0](prefix + v[1].format(n=roi)) 
                        for k,v in _roi_field_map.items()}
                setattr(self, 'roi{n}'.format(n=roi), _Roi(**kws))

        if read_attrs is None:
            read_attrs = ['spectrum', 'preset_time']

        if read_attrs is not None and rois is not None:
            roi_attrs = ['roi{n}.cnt'.format(n=roi) for roi in rois]
            read_attrs += roi_attrs
 
        if configuration_attrs is None:
            configuration_attrs = ['preset_time'] 
 
        if configuration_attrs is not None and rois is not None:
            roi_attrs = ['roi{n}.lo_chan'.format(n=roi) for roi in rois]
            roi_attrs += ['roi{n}.hi_chan'.format(n=roi) for roi in rois]
            configuration_attrs += roi_attrs

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, **kwargs)

    def stage(self):
        '''Stage the scaler for data acquisition'''
        self._old_mode = self.mode.get()
        self.mode.put(0)

    def configure(self, d=None):
        """Configure Scaler

        Configure the scaler by setting autocount to off.
        """
        # TODO
        return {}, {}

    def unstage(self):
        """Unstage from acquisition; reset the autocount status"""
        self.count_mode.put(self._old_count_mode)
