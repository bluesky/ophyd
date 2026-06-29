#!/usr/bin/env python3
from caproto import SkipWrite
from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run


class DropMonitorIOC(PVGroup):
    """A `value` PV that, while `starve`=1, accepts writes but posts no
    monitor. Models an IOC that processed a write but did not post the CA
    monitor update. A fresh caget still returns the new value."""

    value = pvproperty(value=0.0)
    starve = pvproperty(value=0)

    @value.putter
    async def value(self, instance, value):
        if self.starve.value:
            instance._data["value"] = value
            raise SkipWrite()
        return value


if __name__ == "__main__":
    ioc_options, run_options = ioc_arg_parser(
        default_prefix="drop:", desc="Drop-monitor test IOC"
    )
    ioc = DropMonitorIOC(**ioc_options)
    run(ioc.pvdb, **run_options)
