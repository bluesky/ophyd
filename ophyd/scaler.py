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
    _default_configuration_attrs = ('preset_time', 'presets', 'gates',
                                    'names', 'freq', 'auto_count_time',
                                    'count_mode', 'delay',
                                    'auto_count_delay', 'egu')
    _default_read_attrs = ('channels', 'time')
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

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.stage_sigs.update([('count_mode', 0)])


class ScalerChannel(Device):
    _default_configuration_attrs = ('chname', 'preset', 'gate')
    _default_read_attrs = ('s',)

    # TODO set up monitor on this to automatically change the name
    chname = FC(EpicsSignal, '{self.prefix}.NM{self._ch_num}')
    s = FC(EpicsSignalRO, '{self.prefix}.S{self._ch_num}')
    preset = FC(EpicsSignal, '{self.prefix}.PR{self._ch_num}')
    gate = FC(EpicsSignal, '{self.prefix}.G{self._ch_num}', string=True)

    def __init__(self, prefix, ch_num,
                 **kwargs):
        self._ch_num = ch_num

        super().__init__(prefix, **kwargs)
        self.match_name()

    def match_name(self):
        self.s.name = self.chname.get()


def _sc_chans(attr_fix, id_range):
    defn = OrderedDict()
    for k in id_range:
        defn['{}{:02d}'.format(attr_fix, k)] = (ScalerChannel,
                                                '', {'ch_num': k})
    return defn


class ScalerCH(Device):
    _default_configuration_attrs = ('preset_time',
                                    'freq', 'auto_count_time',
                                    'count_mode', 'delay',
                                    'auto_count_delay', 'egu', 'channels')

    _default_read_attrs = ('time', 'channels')

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

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.channels.read_attrs = ['chan01']
        self.channels.configuration_attrs = ['chan01']

    def match_names(self):
        for s in self.channels.component_names:
            getattr(self.channels, s).match_name()

    def select_channels(self, chan_names):
        '''Select channels based on the EPICS name PV

        Parameters
        ----------
        chan_names : Iterable[str]

            The names (as reported by the channel.chname signal)
            of the channels to select.
        '''
        self.match_names()
        name_map = {getattr(self.channels, s).name.get(): s
                    for s in self.channels.component_names}

        read_attrs = ['chan01']  # always include time
        for ch in chan_names:
            try:
                read_attrs.append(name_map[ch])
            except KeyError:
                raise RuntimeError("The channel {} is not configured "
                                   "on the scaler.  The named channels are "
                                   "{}".format(ch, tuple(name_map)))
        self.channels.read_attrs = list(read_attrs)
        self.channels.configuration_attrs = list(read_attrs)
        self.hints = {'fields': [getattr(self.channels, ch).s.name
                                 for ch in read_attrs[1:]]}
