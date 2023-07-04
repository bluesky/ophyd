"""EPICS Signals over CA or PVA"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple, Type

from .core import SignalBackend, SignalR, SignalRW, SignalW, SignalX, T, get_unique

try:
    from ._aioca import CaSignalBackend
except ImportError as ca_error:

    class CaSignalBackend:  # type: ignore
        def __init__(*args, ca_error=ca_error, **kwargs):
            raise NotImplementedError("CA support not available") from ca_error


try:
    from ._p4p import PvaSignalBackend
except ImportError as pva_error:

    class PvaSignalBackend:  # type: ignore
        def __init__(*args, pva_error=pva_error, **kwargs):
            raise NotImplementedError("PVA support not available") from pva_error


class EpicsTransport(Enum):
    """The sorts of transport EPICS support"""

    #: Use Channel Access (using aioca library)
    ca = CaSignalBackend
    #: Use PVAccess (using p4p library)
    pva = PvaSignalBackend


_default_epics_transport = EpicsTransport.ca


def _transport_pv(pv: str) -> Tuple[EpicsTransport, str]:
    split = pv.split("://", 1)
    if len(split) > 1:
        # We got something like pva://mydevice, so use specified comms mode
        transport_str, pv = split
        transport = EpicsTransport[transport_str]
    else:
        # No comms mode specified, use the default
        transport = _default_epics_transport
    return transport, pv


def _make_backend(
    datatype: Optional[Type[T]], read_pv: str, write_pv: str
) -> SignalBackend[T]:
    r_transport, r_pv = _transport_pv(read_pv)
    w_transport, w_pv = _transport_pv(write_pv)
    transport = get_unique({read_pv: r_transport, write_pv: w_transport}, "transports")
    return transport.value(datatype, r_pv, w_pv)


def epics_signal_rw(
    datatype: Type[T], read_pv: str, write_pv: Optional[str] = None
) -> SignalRW[T]:
    """Create a `SignalRW` backed by 1 or 2 EPICS PVs

    Parameters
    ----------
    datatype:
        Check that the PV is of this type
    read_pv:
        The PV to read and monitor
    write_pv:
        If given, use this PV to write to, otherwise use read_pv
    """
    backend = _make_backend(datatype, read_pv, write_pv or read_pv)
    return SignalRW(backend)


def epics_signal_r(datatype: Type[T], read_pv: str) -> SignalR[T]:
    """Create a `SignalR` backed by 1 EPICS PV

    Parameters
    ----------
    datatype:
        Check that the PV is of this type
    read_pv:
        The PV to read and monitor
    """
    backend = _make_backend(datatype, read_pv, read_pv)
    return SignalR(backend)


def epics_signal_w(datatype: Type[T], write_pv: str) -> SignalW[T]:
    """Create a `SignalW` backed by 1 EPICS PVs

    Parameters
    ----------
    datatype:
        Check that the PV is of this type
    write_pv:
        The PV to write to
    """
    backend = _make_backend(datatype, write_pv, write_pv)
    return SignalW(backend)


def epics_signal_x(write_pv: str) -> SignalX:
    """Create a `SignalX` backed by 1 EPICS PVs

    Parameters
    ----------
    write_pv:
        The PV to write its initial value to on execute
    """
    backend: SignalBackend = _make_backend(None, write_pv, write_pv)
    return SignalX(backend)
