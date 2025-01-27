from ophyd import Device, DeviceStatus, EpicsSignal, EpicsSignalRO, FormattedComponent


class TernaryDevice(Device):
    """
    A general purpose ophyd device with set and reset signals, and a state signal
    with 3 posible signals.

    Example
    -------
    class StateEnum(Enum):
        In = True
        Out = False
        Unknown = None

    class ExampleTernary(TernaryDevice):
        def __init__(self, index, *args, **kwargs):
            super().__init__(
                *args,
                name=f"Filter{index}",
                set_name=f"TernaryArray:device{index}_set",
                reset_name=f"TernaryArray:device{index}_reset",
                state_name=f"TernaryArray:device{index}_rbv",
                state_enum=StateEnum,
                **kwargs,
            )
    ternary1 = ExampleTernary(1)
    """

    set_cmd = FormattedComponent(EpicsSignal, "{self._set_name}")
    reset_cmd = FormattedComponent(EpicsSignal, "{self._reset_name}")
    state_rbv = FormattedComponent(EpicsSignalRO, "{self._state_name}", string=True)

    def __init__(
        self, *args, set_name, reset_name, state_name, state_enum, **kwargs
    ) -> None:
        self._state_enum = state_enum
        self._set_name = set_name
        self._reset_name = reset_name
        self._state_name = state_name
        self._state = None
        super().__init__(*args, **kwargs)

    def set(self, value=True):
        if value not in {True, False, 0, 1}:
            raise ValueError("value must be one of the following: True, False, 0, 1")

        target_value = bool(value)

        st = DeviceStatus(self)

        # If the device already has the requested state, return a finished status.
        if self._state == bool(value):
            st._finished()
            return st
        self._set_st = st

        def state_cb(value, timestamp, **kwargs):
            """
            Updates self._state and checks if the status should be marked as finished.
            """
            try:
                self._state = self._state_enum[value].value
            except KeyError:
                raise ValueError(f"self._state_enum does not contain value: {value}")
            if self._state == target_value:
                self._set_st = None
                self.state_rbv.clear_sub(state_cb)
                st._finished()

        # Subscribe the callback to the readback signal.
        # The callback will be called each time the PV value changes.
        self.state_rbv.subscribe(state_cb)

        # Write to the signal.
        if value:
            self.set_cmd.set(1)
        else:
            self.reset_cmd.set(1)
        return st

    def reset(self):
        self.set(False)

    def get(self):
        return self._state
