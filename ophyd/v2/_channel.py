from abc import abstractmethod
from typing import Callable, Generic, Protocol, Type

from bluesky.protocols import Descriptor, Reading

from .core import T

#: A function that will be called with the Reading and value when the
#: monitor updates
ReadingValueCallback = Callable[[Reading, T], None]


class Monitor(Protocol):
    """The kind of handle we expect camonitor/pvmonitor to return"""

    def close(self):
        """Close the monitor so no more subscription callbacks happen"""


class Channel(Generic[T]):
    """An abstraction to a CA/PVA/Sim channel"""

    def __init__(self, pv: str, datatype: Type[T]):
        #: The PV to connect to
        self.pv = pv
        #: The Python datatype to request CA/PVA to return
        self.datatype = datatype

    @property
    @abstractmethod
    def source(self) -> str:
        """Like ca://PV_PREFIX:SIGNAL, or None if not set"""

    @abstractmethod
    async def connect(self):
        """Connect to PV

        Raises
        ------
        `NotConnected` if cancelled
        """

    @abstractmethod
    async def put(self, value: T, wait=True):
        """Put a value to the PV, if wait then wait for completion"""

    @abstractmethod
    async def get_descriptor(self) -> Descriptor:
        """Metadata like source, dtype, shape, precision, units"""

    @abstractmethod
    async def get_reading(self) -> Reading:
        """The current value, timestamp and severity"""

    @abstractmethod
    async def get_value(self) -> T:
        """The current value"""

    @abstractmethod
    def monitor_reading_value(self, callback: ReadingValueCallback[T]) -> Monitor:
        """Observe changes to the current value, timestamp and severity."""


DISCONNECTED_ERROR = NotImplementedError(
    "No PV has been set as EpicsSignal.connect has not been called"
)


class DisconnectedChannel(Channel):
    @property
    def source(self) -> str:
        return ""

    async def connect(self):
        raise DISCONNECTED_ERROR

    async def put(self, value: T, wait=True):
        raise DISCONNECTED_ERROR

    async def get_descriptor(self) -> Descriptor:
        raise DISCONNECTED_ERROR

    async def get_reading(self) -> Reading:
        raise DISCONNECTED_ERROR

    async def get_value(self) -> T:
        raise DISCONNECTED_ERROR

    def monitor_reading_value(self, callback: ReadingValueCallback[T]) -> Monitor:
        raise DISCONNECTED_ERROR


DISCONNECTED_CHANNEL = DisconnectedChannel("", object)


def uninstantiatable_channel(transport: str):
    class UninstantiatableChannel:
        def __init__(self, *args, **kwargs):
            raise LookupError(
                f"Can't make a {transport} pv "
                "as the correct libraries are not installed"
            )

    return UninstantiatableChannel
