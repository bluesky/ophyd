#!/usr/bin/env python3
from caproto.server import pvproperty, PVGroup, ioc_arg_parser, run, SubGroup
from caproto import ChannelType


class EpicsScalerGroup(PVGroup):
    count = pvproperty(name='.CNT', dtype=int)
    count_mode = pvproperty(value='OneShot',
                            name='.CONT',
                            dtype=ChannelType.ENUM,
                            enum_strings=['OneShot', 'AutoCount'])
    delay = pvproperty(name='.DLY', dtype=float)
    auto_count_delay = pvproperty(name='.DLY1', dtype=float)

    class ChannelsGroup(PVGroup):
        chan1 = pvproperty(value=0, name='.S1', dtype=int, read_only=True)
        chan2 = pvproperty(value=0, name='.S2', dtype=int, read_only=True)
        chan3 = pvproperty(value=0, name='.S3', dtype=int, read_only=True)
        chan4 = pvproperty(value=0, name='.S4', dtype=int, read_only=True)
        chan5 = pvproperty(value=0, name='.S5', dtype=int, read_only=True)
        chan6 = pvproperty(value=0, name='.S6', dtype=int, read_only=True)
        chan7 = pvproperty(value=0, name='.S7', dtype=int, read_only=True)
        chan8 = pvproperty(value=0, name='.S8', dtype=int, read_only=True)
        chan9 = pvproperty(value=0, name='.S9', dtype=int, read_only=True)
        chan10 = pvproperty(value=0, name='.S10', dtype=int, read_only=True)
        chan11 = pvproperty(value=0, name='.S11', dtype=int, read_only=True)
        chan12 = pvproperty(value=0, name='.S12', dtype=int, read_only=True)
        chan13 = pvproperty(value=0, name='.S13', dtype=int, read_only=True)
        chan14 = pvproperty(value=0, name='.S14', dtype=int, read_only=True)
        chan15 = pvproperty(value=0, name='.S15', dtype=int, read_only=True)
        chan16 = pvproperty(value=0, name='.S16', dtype=int, read_only=True)
        chan17 = pvproperty(value=0, name='.S17', dtype=int, read_only=True)
        chan18 = pvproperty(value=0, name='.S18', dtype=int, read_only=True)
        chan19 = pvproperty(value=0, name='.S19', dtype=int, read_only=True)
        chan20 = pvproperty(value=0, name='.S20', dtype=int, read_only=True)
        chan21 = pvproperty(value=0, name='.S21', dtype=int, read_only=True)
        chan22 = pvproperty(value=0, name='.S22', dtype=int, read_only=True)
        chan23 = pvproperty(value=0, name='.S23', dtype=int, read_only=True)
        chan24 = pvproperty(value=0, name='.S24', dtype=int, read_only=True)
        chan25 = pvproperty(value=0, name='.S25', dtype=int, read_only=True)
        chan26 = pvproperty(value=0, name='.S26', dtype=int, read_only=True)
        chan27 = pvproperty(value=0, name='.S27', dtype=int, read_only=True)
        chan28 = pvproperty(value=0, name='.S28', dtype=int, read_only=True)
        chan29 = pvproperty(value=0, name='.S29', dtype=int, read_only=True)
        chan30 = pvproperty(value=0, name='.S30', dtype=int, read_only=True)
        chan31 = pvproperty(value=0, name='.S31', dtype=int, read_only=True)
        chan32 = pvproperty(value=0, name='.S32', dtype=int, read_only=True)

    channels = SubGroup(ChannelsGroup, prefix='')

    class NamesGroup(PVGroup):
        name1 = pvproperty(value='name', name='.NM1', dtype=ChannelType.STRING)
        name2 = pvproperty(value='name', name='.NM2', dtype=ChannelType.STRING)
        name3 = pvproperty(value='name', name='.NM3', dtype=ChannelType.STRING)
        name4 = pvproperty(value='name', name='.NM4', dtype=ChannelType.STRING)
        name5 = pvproperty(value='name', name='.NM5', dtype=ChannelType.STRING)
        name6 = pvproperty(value='name', name='.NM6', dtype=ChannelType.STRING)
        name7 = pvproperty(value='name', name='.NM7', dtype=ChannelType.STRING)
        name8 = pvproperty(value='name', name='.NM8', dtype=ChannelType.STRING)
        name9 = pvproperty(value='name', name='.NM9', dtype=ChannelType.STRING)
        name10 = pvproperty(value='name', name='.NM10',
                            dtype=ChannelType.STRING)
        name11 = pvproperty(value='name', name='.NM11',
                            dtype=ChannelType.STRING)
        name12 = pvproperty(value='name', name='.NM12',
                            dtype=ChannelType.STRING)
        name13 = pvproperty(value='name', name='.NM13',
                            dtype=ChannelType.STRING)
        name14 = pvproperty(value='name', name='.NM14',
                            dtype=ChannelType.STRING)
        name15 = pvproperty(value='name', name='.NM15',
                            dtype=ChannelType.STRING)
        name16 = pvproperty(value='name', name='.NM16',
                            dtype=ChannelType.STRING)
        name17 = pvproperty(value='name', name='.NM17',
                            dtype=ChannelType.STRING)
        name18 = pvproperty(value='name', name='.NM18',
                            dtype=ChannelType.STRING)
        name19 = pvproperty(value='name', name='.NM19',
                            dtype=ChannelType.STRING)
        name20 = pvproperty(value='name', name='.NM20',
                            dtype=ChannelType.STRING)
        name21 = pvproperty(value='name', name='.NM21',
                            dtype=ChannelType.STRING)
        name22 = pvproperty(value='name', name='.NM22',
                            dtype=ChannelType.STRING)
        name23 = pvproperty(value='name', name='.NM23',
                            dtype=ChannelType.STRING)
        name24 = pvproperty(value='name', name='.NM24',
                            dtype=ChannelType.STRING)
        name25 = pvproperty(value='name', name='.NM25',
                            dtype=ChannelType.STRING)
        name26 = pvproperty(value='name', name='.NM26',
                            dtype=ChannelType.STRING)
        name27 = pvproperty(value='name', name='.NM27',
                            dtype=ChannelType.STRING)
        name28 = pvproperty(value='name', name='.NM28',
                            dtype=ChannelType.STRING)
        name29 = pvproperty(value='name', name='.NM29',
                            dtype=ChannelType.STRING)
        name30 = pvproperty(value='name', name='.NM30',
                            dtype=ChannelType.STRING)
        name31 = pvproperty(value='name', name='.NM31',
                            dtype=ChannelType.STRING)
        name32 = pvproperty(value='name', name='.NM32',
                            dtype=ChannelType.STRING)

    names = SubGroup(NamesGroup, prefix='')

    time = pvproperty(name='.T', dtype=float)
    freq = pvproperty(name='.FREQ', dtype=float)
    preset_time = pvproperty(name='.TP', dtype=float)
    auto_count_time = pvproperty(name='.TP1', dtype=float)

    class PresetsGroup(PVGroup):
        preset1 = pvproperty(name='.PR1', dtype=int)
        preset2 = pvproperty(name='.PR2', dtype=int)
        preset3 = pvproperty(name='.PR3', dtype=int)
        preset4 = pvproperty(name='.PR4', dtype=int)
        preset5 = pvproperty(name='.PR5', dtype=int)
        preset6 = pvproperty(name='.PR6', dtype=int)
        preset7 = pvproperty(name='.PR7', dtype=int)
        preset8 = pvproperty(name='.PR8', dtype=int)
        preset9 = pvproperty(name='.PR9', dtype=int)
        preset10 = pvproperty(name='.PR10', dtype=int)
        preset11 = pvproperty(name='.PR11', dtype=int)
        preset12 = pvproperty(name='.PR12', dtype=int)
        preset13 = pvproperty(name='.PR13', dtype=int)
        preset14 = pvproperty(name='.PR14', dtype=int)
        preset15 = pvproperty(name='.PR15', dtype=int)
        preset16 = pvproperty(name='.PR16', dtype=int)
        preset17 = pvproperty(name='.PR17', dtype=int)
        preset18 = pvproperty(name='.PR18', dtype=int)
        preset19 = pvproperty(name='.PR19', dtype=int)
        preset20 = pvproperty(name='.PR20', dtype=int)
        preset21 = pvproperty(name='.PR21', dtype=int)
        preset22 = pvproperty(name='.PR22', dtype=int)
        preset23 = pvproperty(name='.PR23', dtype=int)
        preset24 = pvproperty(name='.PR24', dtype=int)
        preset25 = pvproperty(name='.PR25', dtype=int)
        preset26 = pvproperty(name='.PR26', dtype=int)
        preset27 = pvproperty(name='.PR27', dtype=int)
        preset28 = pvproperty(name='.PR28', dtype=int)
        preset29 = pvproperty(name='.PR29', dtype=int)
        preset30 = pvproperty(name='.PR30', dtype=int)
        preset31 = pvproperty(name='.PR31', dtype=int)
        preset32 = pvproperty(name='.PR32', dtype=int)

    presets = SubGroup(PresetsGroup, prefix='')

    class GatesGroup(PVGroup):
        gate1 = pvproperty(name='.G1', dtype=int)
        gate2 = pvproperty(name='.G2', dtype=int)
        gate3 = pvproperty(name='.G3', dtype=int)
        gate4 = pvproperty(name='.G4', dtype=int)
        gate5 = pvproperty(name='.G5', dtype=int)
        gate6 = pvproperty(name='.G6', dtype=int)
        gate7 = pvproperty(name='.G7', dtype=int)
        gate8 = pvproperty(name='.G8', dtype=int)
        gate9 = pvproperty(name='.G9', dtype=int)
        gate10 = pvproperty(name='.G10', dtype=int)
        gate11 = pvproperty(name='.G11', dtype=int)
        gate12 = pvproperty(name='.G12', dtype=int)
        gate13 = pvproperty(name='.G13', dtype=int)
        gate14 = pvproperty(name='.G14', dtype=int)
        gate15 = pvproperty(name='.G15', dtype=int)
        gate16 = pvproperty(name='.G16', dtype=int)
        gate17 = pvproperty(name='.G17', dtype=int)
        gate18 = pvproperty(name='.G18', dtype=int)
        gate19 = pvproperty(name='.G19', dtype=int)
        gate20 = pvproperty(name='.G20', dtype=int)
        gate21 = pvproperty(name='.G21', dtype=int)
        gate22 = pvproperty(name='.G22', dtype=int)
        gate23 = pvproperty(name='.G23', dtype=int)
        gate24 = pvproperty(name='.G24', dtype=int)
        gate25 = pvproperty(name='.G25', dtype=int)
        gate26 = pvproperty(name='.G26', dtype=int)
        gate27 = pvproperty(name='.G27', dtype=int)
        gate28 = pvproperty(name='.G28', dtype=int)
        gate29 = pvproperty(name='.G29', dtype=int)
        gate30 = pvproperty(name='.G30', dtype=int)
        gate31 = pvproperty(name='.G31', dtype=int)
        gate32 = pvproperty(name='.G32', dtype=int)

    gates = SubGroup(GatesGroup, prefix='')

    update_rate = pvproperty(name='.RATE', dtype=int)
    auto_count_update_rate = pvproperty(name='.RAT1', dtype=int)
    egu = pvproperty(value='EGU', name='.EGU', dtype=ChannelType.STRING)


if __name__ == '__main__':
    ioc_options, run_options = ioc_arg_parser(
        default_prefix='scaler_tests:',
        desc="ophyd.tests.test_scaler test IOC")
    ioc = EpicsScalerGroup(**ioc_options)
    run(ioc.pvdb, **run_options)
