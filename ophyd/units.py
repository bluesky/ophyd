import numbers
from typing import Any, Optional, Tuple

import pint

from .signal import DerivedSignal

_global_unit_registry = None


def convert_unit(value: float, from_units: str, to_units: str):
    """
    Convert ``value`` from ``from_units`` to ``to_units`` using ``pint``.

    Parameters
    ----------
    value : float
        The starting value for the conversion.

    from_units : str
        The starting unit of the provided value.

    to_units : str
        The desired unit to convert the value to.

    Returns
    -------
    new_value : float
        The starting value, but converted to the new unit.
    """

    global _global_unit_registry
    if _global_unit_registry is None:
        # NOTE: Instantiating the unit registry is a heavy operation and should
        # not be performed repeatedly.
        _global_unit_registry = pint.UnitRegistry()

    expr = _global_unit_registry.parse_expression(from_units)
    return (value * expr).to(to_units).magnitude


class UnitConversionDerivedSignal(DerivedSignal):
    """
    A DerivedSignal which performs unit conversion.

    Custom units may be specified for the original signal, or if specified, the
    original signal's units may be retrieved upon first connection.

    Parameters
    ----------
    derived_from : Signal or str
        The signal from which this one is derived.  This may be a string
        attribute name that indicates a sibling to use.  When used in a
        ``Device``, this is then simply the attribute name of another
        ``Component``.

    derived_units : str
        The desired units to use for this signal.  These can also be referred
        to as the "user-facing" units.

    original_units : str, optional
        The units from the original signal.  If not specified, control system
        information regarding units will be retrieved upon first connection.

    user_offset : any, optional
        An optional user offset that will be *subtracted* when updating the
        original signal, and *added* when calculating the derived value.
        This offset should be supplied in ``derived_units`` and not
        ``original_units``.

        For example, if the original signal updates to a converted value of
        500 ``derived_units`` and the ``user_offset`` is set to 100, this
        ``DerivedSignal`` will show a value of 600.  When providing a new
        setpoint, the ``user_offset`` will be subtracted.

    write_access : bool, optional
        Write access may be disabled by setting this to ``False``, regardless
        of the write access of the underlying signal.

    name : str, optional
        The signal name.

    parent : Device, optional
        The parent device.  Required if ``derived_from`` is an attribute name.

    limits : 2-tuple, optional
        Ophyd signal-level limits in derived units.  DerivedSignal defaults
        to converting the original signal's limits, but these may be overridden
        here without modifying the original signal.

    **kwargs :
        Keyword arguments are passed to the superclass.
    """

    derived_units: str
    original_units: str

    def __init__(
        self,
        derived_from,
        *,
        derived_units: str,
        original_units: Optional[str] = None,
        user_offset: Optional[numbers.Real] = 0,
        limits: Optional[Tuple[numbers.Real, numbers.Real]] = None,
        **kwargs,
    ):
        self.derived_units = derived_units
        self.original_units = original_units
        self._user_offset = user_offset
        self._custom_limits = limits
        super().__init__(derived_from, **kwargs)
        self._metadata["units"] = derived_units

        # Ensure that we include units in metadata callbacks, even if the
        # original signal does not include them.
        if "units" not in self._metadata_keys:
            self._metadata_keys = self._metadata_keys + ("units",)

    def forward(self, value):
        """Compute derived signal value -> original signal value"""
        if self.user_offset is None:
            raise ValueError(
                f"{self.name}.user_offset must be set to a non-None value."
            )
        return convert_unit(
            value - self.user_offset, self.derived_units, self.original_units
        )

    def inverse(self, value):
        """Compute original signal value -> derived signal value"""
        if self.user_offset is None:
            raise ValueError(
                f"{self.name}.user_offset must be set to a non-None value."
            )
        return (
            convert_unit(value, self.original_units, self.derived_units)
            + self.user_offset
        )

    @property
    def limits(self):
        """
        Defaults to limits from the original signal (low, high).

        Limit values may be reversed such that ``low <= value <= high`` after
        performing the calculation.

        Limits may also be overridden here without affecting the original
        signal.
        """
        if self._custom_limits is not None:
            return self._custom_limits

        # Fall back to the superclass derived_from limits:
        return tuple(sorted(self.inverse(v) for v in self._derived_from.limits))

    @limits.setter
    def limits(self, value):
        if value is None:
            self._custom_limits = None
            return

        if len(value) != 2 or value[0] >= value[1]:
            raise ValueError("Custom limits must be a 2-tuple (low, high)")

        self._custom_limits = tuple(value)

    @property
    def user_offset(self) -> Optional[Any]:
        """A user-specified offset in *derived*, user-facing units."""
        return self._user_offset

    @user_offset.setter
    def user_offset(self, offset):
        offset_change = -self._user_offset + offset
        self._user_offset = offset
        self._recalculate_position()
        if self._custom_limits is not None:
            self._custom_limits = (
                self._custom_limits[0] + offset_change,
                self._custom_limits[1] + offset_change,
            )

    def _recalculate_position(self):
        """
        Recalculate the derived position and send subscription updates.

        No-operation if the original signal is not connected.
        """
        if not self._derived_from.connected:
            return

        value = self._derived_from.get()
        if value is not None:
            # Note: no kwargs here; no metadata updates
            self._derived_value_callback(value)

    def _derived_metadata_callback(self, *, connected, **kwargs):
        if connected and "units" in kwargs:
            if self.original_units is None:
                self.original_units = kwargs["units"]
        # Do not pass through units, as we have our own.
        kwargs["units"] = self.derived_units
        super()._derived_metadata_callback(connected=connected, **kwargs)

    def describe(self):
        full_desc = super().describe()
        desc = full_desc[self.name]
        desc["units"] = self.derived_units
        # Note: this should be handled in ophyd:
        for key in ("lower_ctrl_limit", "upper_ctrl_limit"):
            if key in desc:
                desc[key] = self.inverse(desc[key])
        return full_desc
