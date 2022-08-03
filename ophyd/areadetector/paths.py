import logging
import pathlib
import time as ttime

from ..signal import EpicsSignal

logger = logging.getLogger(__name__)
OS_NAME_TO_PATH_CLASS = {
    "nt": pathlib.PureWindowsPath,
    "posix": pathlib.PurePosixPath,
}

OS_SEPARATORS = {"nt": "\\", "posix": "/"}


def path_compare(path_a, path_b, semantics):
    """
    Compare paths, given OS-specific semantics

    Parameters
    ----------
    path_a : str or pathlib.Path
        The first path
    path_b : str or pathlib.Path
        The second path
    semantics : {'nt', 'posix'}
        The OS name for the path

    Returns
    -------
    result : bool
        Whether the paths are equal or not
    """
    try:
        path_class = OS_NAME_TO_PATH_CLASS[semantics]
    except KeyError:
        raise ValueError(f"Unknown path semantics: {semantics}") from None

    return path_class(path_a) == path_class(path_b)


def set_and_wait_path(signal, val, *, path_semantics, poll_time=0.01, timeout=10):
    """
    Set a path signal to a value and wait until it reads back correctly.

    Parameters
    ----------
    signal : EpicsPathSignal (or any object with `get` and `put`)
        The signal itself
    val : object
        value to set signal to
    path_semantics : {'nt', 'posix'}
        The OS name for the path
    poll_time : float, optional
        how soon to check whether the value has been successfully set
    timeout : float, optional
        maximum time to wait for value to be successfully set

    Raises
    ------
    TimeoutError if timeout is exceeded
    """
    # ensure a Path object is converted to a string before setting
    val = str(val)
    # Make sure val has trailing separator before it's set
    if not any(val.endswith(sep) for sep in OS_SEPARATORS.values()):
        val = val + OS_SEPARATORS[path_semantics]
    signal.put(val)
    deadline = ttime.time() + timeout if timeout is not None else None
    current_value = signal.get()

    while not path_compare(current_value, val, semantics=path_semantics):
        logger.debug(
            "Waiting for %s to be set from %r to %r...", signal.name, current_value, val
        )
        ttime.sleep(poll_time)
        if poll_time < 0.1:
            poll_time *= 2  # logarithmic back-off
        current_value = signal.get()
        if deadline is not None and ttime.time() > deadline:
            raise TimeoutError(
                "Attempted to set %r to value %r and timed "
                "out after %r seconds. Current value is %r."
                % (signal, val, timeout, current_value)
            )


class EpicsPathSignal(EpicsSignal):
    def __init__(self, write_pv, *, path_semantics, string=True, **kwargs):
        """
        An areaDetector-compatible EpicsSignal expecting 2 PVs holding a path

        That is, an EpicsPathSignal uses the areaDetector convention of
        'pvname' being the setpoint and 'pvname_RBV' being the read-back path.

        Operating system-specific path semantics are respected when confirming
        that a :meth:`.set()` operation has completed.
        """
        if write_pv.endswith("_RBV"):
            # Strip off _RBV if it was passed in erroneously
            write_pv = write_pv[:-4]

        self.path_semantics = path_semantics
        if string is not True:
            raise ValueError(
                "Specifying an EpicsPathSignal with string=False" " does not make sense"
            )

        super().__init__(
            write_pv=write_pv, read_pv=f"{write_pv}_RBV", string=True, **kwargs
        )

    @property
    def path_semantics(self):
        return self._path_semantics

    @path_semantics.setter
    def path_semantics(self, value):
        if value not in OS_NAME_TO_PATH_CLASS:
            raise ValueError(
                f"Unknown path semantics: {value}. " f"Options: {OS_NAME_TO_PATH_CLASS}"
            )
        self._path_semantics = value

    def _repr_info(self):
        yield from super()._repr_info()
        yield ("path_semantics", self.path_semantics)

    def _set_and_wait(self, value, timeout):
        """
        Overridable hook for subclasses to override :meth:`.set` functionality.

        This will be called in a separate thread (`_set_thread`), but will not
        be called in parallel.

        Parameters
        ----------
        value : any
            The value
        timeout : float, optional
            Maximum time to wait for value to be successfully set, or None
        """
        return set_and_wait_path(
            self, value, timeout=timeout, path_semantics=self.path_semantics
        )
