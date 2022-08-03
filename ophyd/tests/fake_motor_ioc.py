#!/usr/bin/env python3
import numpy as np
from caproto.server import PVGroup, ioc_arg_parser, pvproperty, run


class FakeMotorIOC(PVGroup):
    setpoint = pvproperty(value=0.0, precision=1)
    readback = pvproperty(value=0.0, read_only=True, precision=1)
    moving = pvproperty(value=0.0, read_only=True)
    actuate = pvproperty(value=0)
    stop = pvproperty(value=0)
    step_size = pvproperty(value=0.1)

    @actuate.scan(period=0.1)
    async def actuate(self, instance, async_lib):
        step_size = self.step_size.value
        setpoint = self.setpoint.value
        readback = self.readback.value
        moving = self.moving.value
        actuate = self.actuate.value
        stop = self.stop.value

        if stop:
            await self.stop.write(0)
            await self.moving.write(0)
        elif actuate or moving:
            if moving != 1:
                await self.actuate.write(0)
                await self.moving.write(1)

            delta = setpoint - readback
            if abs(delta) <= step_size:
                await self.readback.write(setpoint)
                await self.moving.write(0)
            else:
                await self.readback.write(readback + np.sign(delta) * step_size)


if __name__ == "__main__":
    ioc_options, run_options = ioc_arg_parser(
        default_prefix="fake_motor:", desc="An IOC which mocks a simple motor"
    )
    ioc = FakeMotorIOC(**ioc_options)
    run(ioc.pvdb, **run_options)
