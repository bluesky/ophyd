import os
import pathlib
import time as ttime

from .. import EpicsSignal
from ..status import Status


OS_NAME_TO_PATH_CLASS = {
    'nt': pathlib.PureWindowsPath,
    'posix': pathlib.PurePosixPath,
}


def path_compare(path_a, path_b, semantics):
    '''
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
    '''
    try:
        path_class = OS_NAME_TO_PATH_CLASS[semantics]
    except KeyError:
        raise ValueError(f'Unknown path semantics: {semantics}') from None

    return path_class(path_a) == path_class(path_b)


def set_and_wait_path(signal, val, *, path_semantics, poll_time=0.01,
                      timeout=10):
    """
    Set a signal to a value and wait until it reads correctly.
    For floating point values, it is strongly recommended to set a tolerance.
    If tolerances are unset, the values will be compared exactly.

    Parameters
    ----------
    signal : EpicsPathSignal (or any object with `get` and `put`)
    val : object
        value to set signal to
    poll_time : float, optional
        how soon to check whether the value has been successfully set
    timeout : float, optional
        maximum time to wait for value to be successfully set

    Raises
    ------
    TimeoutError if timeout is exceeded
    """
    signal.put(val)
    expiration_time = ttime.time() + timeout if timeout is not None else None
    current_value = signal.get()

    while not path_compare(current_value, val, semantics=path_semantics):
        logger.debug("Waiting for %s to be set from %r to %r...",
                     signal.name, current_value, val)
        ttime.sleep(poll_time)
        if poll_time < 0.1:
            poll_time *= 2  # logarithmic back-off
        current_value = signal.get()
        if expiration_time is not None and ttime.time() > expiration_time:
            raise TimeoutError("Attempted to set %r to value %r and timed "
                               "out after %r seconds. Current value is %r." %
                               (signal, val, timeout, current_value))


class EpicsPathSignal(EpicsSignal):
    def __init__(self, write_pv, *, path_semantics, **kwargs):
        self.path_semantics = path_semantics
        if kwargs.get('string', True) is not True:
            raise ValueError('Specifying an EpicsPathSignal with string=False'
                             ' does not make sense')
        if path_semantics not in OS_NAME_TO_PATH_CLASS:
            raise ValueError(f'Unknown path semantics: {path_semantics}. '
                             f'Options: {OS_NAME_TO_PATH_CLASS}')

        super().__init__(write_pv=write_pv,
                         read_pv=f'{write_pv}_RBV',
                         string=True,
                         **kwargs)

    def _repr_info(self):
        yield from super()._repr_info()
        yield ('path_semantics', self.path_semantics)

    def _set_and_wait(self, value, timeout):
        '''
        Overridable hook for subclasses to override :meth:`.set` functionality.

        This will be called in a separate thread (`_set_thread`), but will not
        be called in parallel.

        Parameters
        ----------
        value : any
            The value
        timeout : float, optional
            Maximum time to wait for value to be successfully set, or None
        '''
        return set_and_wait_path(self, value, timeout=timeout,
                                 path_semantics=self.path_semantics)
