from __future__ import print_function
import logging

from collections import OrderedDict, namedtuple

from .signal import (EpicsSignal, EpicsSignalRO)
from .device import OphydDevice
from .device import Component as C

logger = logging.getLogger(__name__)


_roi_field_map = OrderedDict([('name', (EpicsSignal, '.R{}NM')),
                  ('cnt', (EpicsSignalRO, '.R{}')),
                  ('net_cnt', (EpicsSignalRO, '.R{}N')),
                  ('preset_cnt', (EpicsSignal, '.R{}P')),
                  ('is_preset', (EpicsSignal, '.R{}IP')),
                  ('bkgnd_chans', (EpicsSignal, '.R{}BG')),
                  ('hi_chan', (EpicsSignal, '.R{}HI')),
                  ('lo_chan', (EpicsSignal, '.R{}LO'))
                  ])

_Roi = namedtuple('_Roi', _roi_field_map.keys())


class EpicsMCA(OphydDevice):
    '''SynApps MCA Record interface'''

    start = C(EpicsSignal, 'Start')
    erase_start = C(EpicsSignal, 'EraseStart', trigger_value=1)

    _stop = C(EpicsSignal, '.STOP')
    preset_time = C(EpicsSignal, '.ERTM', write_pv='.PRTM')
    spectrum = C(EpicsSignalRO, '.VAL')
    background = C(EpicsSignalRO, '.BG')
    mode = C(EpicsSignal, '.MODE', string=True)

    def __init__(self, prefix, *, rois=None, read_attrs=None,
                 configuration_attrs=None, monitor_attrs=None, name=None,
                 parent=None, **kwargs):

        default_read_attrs = ['spectrum', 'preset_time']
        default_configuration_attrs = ['preset_time']

        if read_attrs is None:
            read_attrs = default_read_attrs

        if configuration_attrs is None:
            configuration_attrs = default_configuration_attrs

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         monitor_attrs=monitor_attrs,
                         name=name, parent=parent, **kwargs)

        if rois is not None:
            self.add_roi(rois)

            # add some 'sensible' defaults for read/config_attrs, if not given
            if read_attrs == default_read_attrs:
                # add ROI bits to read_attr and configuration_attr
                self.read_attrs += ['roi{n}.cnt'.format(n=roi) for roi in rois]

            if configuration_attrs == default_configuration_attrs:
                roi_attrs = ['roi{n}.lo_chan'.format(n=roi) for roi in rois]
                roi_attrs += ['roi{n}.hi_chan'.format(n=roi) for roi in rois]
                self.configuration_attrs += roi_attrs

    def stop(self):
        self._stop.put(1)

    def add_roi(self, rois):
        '''Add one or more ROIs to an MCA instance

           Parameters:
           -----------
           rois : sequence of ints
               Must be be in the set [0,31]

           Example:
           -------
           >>> vtx = EpicsMCA('my_mca')
           >>> vtx.add_roi(range(0,5))

           This will add 5 ROIs, vtx.roi0 through vtx.roi4, and their
           EpicsSignals: roiN.(name,cnt,net_cnt,preset_cnt, is_preset,
                               bkgnd_chans, hi_chan, lo_chan)
           '''
        for roi in rois:
            assert 0 <= roi < 32

            kws = {k: v[0](self.prefix + v[1].format(roi))
                   for k, v in _roi_field_map.items()}
            setattr(self, 'roi{}'.format(roi), _Roi(**kws))

    def stage(self):
        '''Stage the MCA for data acquisition'''
        self._old_mode = self.mode.get()
        self.mode.put(0)

    def unstage(self):
        '''Unstage from acquisition; restore the pre-scan mode'''
        self.count_mode.put(self._old_count_mode)
