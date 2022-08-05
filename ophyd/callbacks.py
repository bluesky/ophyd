import logging

from .utils import DisconnectedError

logger = logging.getLogger(__name__)


class UidPublish:
    """Publishes run start UID of most recently begun run to a given signal

    Processed on every start/end document.

    Note: If used with an EpicsSignal, it's recommended to use a waveform in
    place of a stringin record on the EPICS side, as the start document UID
    will be published both on run start and run completion. A stringin record
    will only process on change and monitor events will only be received on run
    start.

    Sample EPICS record definition:

        record(waveform, "$(Sys)$(Dev)UID-I") {
            # Using waveform here as it always reprocesses, so you'll get a
            # monitor event on start/stop of the run
            field(DESC, "Last run UID")
            field(FTVL, "STRING")
            field(MPST, "Always")
            info(autosaveFields_pass0, "VAL")
        }

    Parameters
    ----------
    uid_signal : Signal
        The signal to publish to
    raise_if_disconnected : bool, optional
        Fail if the UID signal is disconnected
    put_kw : kwargs, optional
        Keyword arguments to send to uid_signal.put()
    """

    def __init__(self, signal, raise_if_disconnected=False, **put_kw):
        self._uid = None
        self.last_start = None
        self.uid_signal = signal
        self.put_kw = put_kw
        self.raise_if_disconnected = raise_if_disconnected

    @property
    def uid(self):
        """The uid of the last run"""
        return self._uid

    @uid.setter
    def uid(self, uid):
        self._uid = uid

        if uid is None:
            uid = ""

        try:
            self.uid_signal.put(uid, **self.put_kw)
        except (DisconnectedError, TimeoutError):
            logger.error("UID signal disconnected. Is the IOC running?")
            if self.raise_if_disconnected:
                raise

    def clear(self):
        """Clear the run uid"""
        self.uid = None

    def __call__(self, name, doc):
        """Bluesky callback with document info"""
        if name == "start":
            self.last_start = doc

        if self.last_start and name in ("start", "stop"):
            self.uid = self.last_start["uid"]


class LastUidPublish(UidPublish):
    """Publishes run start UID of most recently completed run to a given signal

    Processed on every stop document.

    Note: If used with an EpicsSignal, it's recommended to use a waveform in
    place of a stringin record on the EPICS side, as the start document UID
    will be published both on run start and run completion. A stringin record
    will only process on change and monitor events will only be received on run
    start.

    Sample EPICS record definition:

        record(waveform, "$(Sys)$(Dev)UID-I") {
            # Using waveform here as it always reprocesses, so you'll get a
            # monitor event on start/stop of the run
            field(DESC, "Last run UID")
            field(FTVL, "STRING")
            field(MPST, "Always")
            info(autosaveFields_pass0, "VAL")
        }

    Parameters
    ----------
    uid_signal : Signal
        The signal to publish to
    raise_if_disconnected : bool, optional
        Fail if the UID signal is disconnected
    put_kw : kwargs, optional
        Keyword arguments to send to uid_signal.put()
    """

    def __call__(self, name, doc):
        """Bluesky callback with document info"""
        if name == "start":
            self.last_start = doc

        if self.last_start is not None and name == "stop":
            self.uid = self.last_start["uid"]
