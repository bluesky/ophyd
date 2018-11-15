#!/usr/bin/env python3
from caproto.server import pvproperty, PVGroup, ioc_arg_parser, run


class SignalTestIOC(PVGroup):
    read_only = pvproperty(value=0.0, read_only=True)
    read_write = pvproperty(value=0.0,
                            lower_ctrl_limit=-100.0,
                            upper_ctrl_limit=100.0)
    waveform = pvproperty(value=[0, 1, 2], read_only=True)
    bool_enum = pvproperty(value=True)


if __name__ == '__main__':
    ioc_options, run_options = ioc_arg_parser(
        default_prefix='signal_tests:',
        desc="ophyd.tests.test_signal test IOC")
    ioc = SignalTestIOC(**ioc_options)
    run(ioc.pvdb, **run_options)
