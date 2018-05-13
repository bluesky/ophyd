import logging

from collections import OrderedDict

from .ophydobj import Kind
from .signal import (EpicsSignal, EpicsSignalRO)
from .device import Device
from .device import (Component as C, DynamicDeviceComponent as DDC,
                     FormattedComponent as FC, RESPECT_KIND,
                     ConfigComponent as CC, OmittedComponent as OC)

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
    _default_configuration_attrs = RESPECT_KIND
    _default_read_attrs = RESPECT_KIND
    # tigger + trigger mode
    count = OC(EpicsSignal, '.CNT', trigger_value=1, kind=Kind.OMITTED)
    count_mode = CC(EpicsSignal, '.CONT', string=True, kind=Kind.CONFIG)

    # delay from triggering to starting counting
    delay = CC(EpicsSignal, '.DLY', kind=Kind.CONFIG)
    auto_count_delay = CC(EpicsSignal, '.DLY1', kind=Kind.CONFIG)

    # the data
    channels = DDC(_scaler_fields(EpicsSignalRO, 'chan', '.S', range(1, 33),
                                  kind=Kind.HINTED),
                   default_read_attrs=RESPECT_KIND,
                   default_configuration_attrs=RESPECT_KIND)
    names = DDC(_scaler_fields(EpicsSignal, 'name', '.NM', range(1, 33),
                               kind=Kind.CONFIG),
                default_read_attrs=RESPECT_KIND,
                default_configuration_attrs=RESPECT_KIND)

    time = C(EpicsSignal, '.T', kind=Kind.CONFIG)
    freq = CC(EpicsSignal, '.FREQ', kind=Kind.CONFIG)

    preset_time = CC(EpicsSignal, '.TP', kind=Kind.CONFIG)
    auto_count_time = CC(EpicsSignal, '.TP1', kind=Kind.CONFIG)

    presets = DDC(_scaler_fields(EpicsSignal, 'preset', '.PR', range(1, 33),
                                 kind=Kind.OMITTED),
                  default_read_attrs=RESPECT_KIND,
                  default_configuration_attrs=RESPECT_KIND)
    gates = DDC(_scaler_fields(EpicsSignal, 'gate', '.G', range(1, 33),
                               kind=Kind.OMITTED),
                default_read_attrs=RESPECT_KIND,
                default_configuration_attrs=RESPECT_KIND)

    update_rate = OC(EpicsSignal, '.RATE', kind=Kind.CONFIG)
    auto_count_update_rate = OC(EpicsSignal, '.RAT1', kind=Kind.CONFIG)

    egu = CC(EpicsSignal, '.EGU', kind=Kind.CONFIG)

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.stage_sigs.update([('count_mode', 0)])


class ScalerChannel(Device):
    _default_configuration_attrs = RESPECT_KIND
    _default_read_attrs = RESPECT_KIND

    # TODO set up monitor on this to automatically change the name
    chname = FC(EpicsSignal, '{self.prefix}.NM{self._ch_num}',
                kind=Kind.CONFIG)
    s = FC(EpicsSignalRO, '{self.prefix}.S{self._ch_num}',
           kind=Kind.HINTED)
    preset = FC(EpicsSignal, '{self.prefix}.PR{self._ch_num}',
                kind=Kind.CONFIG)
    gate = FC(EpicsSignal, '{self.prefix}.G{self._ch_num}', string=True,
              kind=Kind.CONFIG)

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
                                                '', {'ch_num': k,
                                                     'kind': Kind.NORMAL})
    return defn


class ScalerCH(Device):
    _default_configuration_attrs = RESPECT_KIND
    _default_read_attrs = RESPECT_KIND

    # The data
    channels = DDC(_sc_chans('chan', range(1, 33)),
                   default_read_attrs=RESPECT_KIND,
                   default_configuration_attrs=RESPECT_KIND)

    # tigger + trigger mode
    count = OC(EpicsSignal, '.CNT', trigger_value=1)
    count_mode = CC(EpicsSignal, '.CONT', string=True)

    # delay from triggering to starting counting
    delay = CC(EpicsSignal, '.DLY')
    auto_count_delay = CC(EpicsSignal, '.DLY1')

    time = C(EpicsSignal, '.T')
    freq = CC(EpicsSignal, '.FREQ')

    preset_time = CC(EpicsSignal, '.TP')
    auto_count_time = CC(EpicsSignal, '.TP1')

    update_rate = OC(EpicsSignal, '.RATE')
    auto_count_update_rate = OC(EpicsSignal, '.RAT1')

    egu = CC(EpicsSignal, '.EGU')

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        active_channels = []
        for s in self.channels.component_names:
            ch_name = getattr(self.channels, s).name
            if ch_name:
                active_channels.append(ch_name)

        self.channels.read_attrs = list(active_channels)
        self.channels.configuration_attrs = list(active_channels)

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
        self.channels.kind = Kind.NORMAL
        self.channels.read_attrs = list(read_attrs)
        self.channels.configuration_attrs = list(read_attrs)
        for ch in read_attrs[1:]:
            getattr(self.channels, ch).s.kind = Kind.HINTED
