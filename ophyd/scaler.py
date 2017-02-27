import logging

from collections import OrderedDict

from ophyd.signal import (EpicsSignal, EpicsSignalRO)
from ophyd.device import Device
from ophyd.device import (Component as C, DynamicDeviceComponent as DDC,
                          FormattedComponent as FC)

logger = logging.getLogger(__name__)


def _scaler_fields(cls, attr_base, field_base, range_, **kwargs):
    defn = OrderedDict()
    for i in range_:
        attr = '{attr}{i}'.format(attr=attr_base, i=i)
        suffix = '{field}{i}'.format(field=field_base, i=i)
        defn[attr] = (cls, suffix, kwargs)

    return defn


class EpicsScaler(Device):
    '''SynApps Scaler Record interface'''

    # tigger + trigger mode
    count = C(EpicsSignal, '.CNT', trigger_value=1)
    count_mode = C(EpicsSignal, '.CONT', string=True)

    # delay from triggering to starting counting
    delay = C(EpicsSignal, '.DLY')
    auto_count_delay = C(EpicsSignal, '.DLY1')

    # the data
    channels = DDC(_scaler_fields(EpicsSignalRO, 'chan', '.S', range(1, 33)))
    names = DDC(_scaler_fields(EpicsSignal, 'name', '.NM', range(1, 33)))

    time = C(EpicsSignal, '.T')
    freq = C(EpicsSignal, '.FREQ')

    preset_time = C(EpicsSignal, '.TP')
    auto_count_time = C(EpicsSignal, '.TP1')

    presets = DDC(_scaler_fields(EpicsSignal, 'preset', '.PR', range(1, 33)))
    gates = DDC(_scaler_fields(EpicsSignal, 'gate', '.G', range(1, 33)))

    update_rate = C(EpicsSignal, '.RATE')
    auto_count_update_rate = C(EpicsSignal, '.RAT1')

    egu = C(EpicsSignal, '.EGU')

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 name=None, parent=None, **kwargs):
        if read_attrs is None:
            read_attrs = ['channels', 'time']

        if configuration_attrs is None:
            configuration_attrs = ['preset_time', 'presets', 'gates',
                                   'names', 'freq', 'auto_count_time',
                                   'count_mode', 'delay',
                                   'auto_count_delay', 'egu']

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         name=name, parent=parent, **kwargs)

        self.stage_sigs.update([('count_mode', 0)])


class ScalerChannel(Device):
    chname = FC(EpicsSignal, '{self.prefix}.NM{self._ch_num}')
    s = FC(EpicsSignalRO, '{self.prefix}.S{self._ch_num}')
    preset = FC(EpicsSignal, '{self.prefix}.PR{self._ch_num}')
    gate = FC(EpicsSignal, '{self.prefix}.G{self._ch_num}', string=True)

    def __init__(self, prefix, ch_num, *, read_attrs=None,
                 configuration_attrs=None,
                 **kwargs):
        self._ch_num = ch_num
        if read_attrs is None:
            read_attrs = ['s']
        if configuration_attrs is None:
            configuration_attrs = ['chname', 'preset', 'gate']
        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         **kwargs)

    def match_name(self):
        self.s.name = self.chname.get()


def _sc_chans(attr_fix, id_range):
    defn = OrderedDict()
    for k in id_range:
        defn['{}{:02d}'.format(attr_fix, k)] = (ScalerChannel,
                                                '', {'ch_num': k})
    return defn


class ScalerCH(Device):
    # The data
    channels = DDC(_sc_chans('chan', range(1, 33)))

    # tigger + trigger mode
    count = C(EpicsSignal, '.CNT', trigger_value=1)
    count_mode = C(EpicsSignal, '.CONT', string=True)

    # delay from triggering to starting counting
    delay = C(EpicsSignal, '.DLY')
    auto_count_delay = C(EpicsSignal, '.DLY1')

    time = C(EpicsSignal, '.T')
    freq = C(EpicsSignal, '.FREQ')

    preset_time = C(EpicsSignal, '.TP')
    auto_count_time = C(EpicsSignal, '.TP1')

    update_rate = C(EpicsSignal, '.RATE')
    auto_count_update_rate = C(EpicsSignal, '.RAT1')

    egu = C(EpicsSignal, '.EGU')

    def __init__(self, *args, read_attrs=None, configuration_attrs=None,
                 **kwargs):

        if configuration_attrs is None:
            configuration_attrs = ['preset_time',
                                   'freq', 'auto_count_time',
                                   'count_mode', 'delay',
                                   'auto_count_delay', 'egu', 'channels']

        if read_attrs is None:
            read_attrs = ['channels']

        super().__init__(*args, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)

        self.channels.read_attrs = ['chan01']
