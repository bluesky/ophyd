import time as ttime
from threading import Timer, Thread
import logging
logger = logging.getLogger(__name__)


class PauseScanCondition(object):
    """Mechanism to pause the scan while some condition is met

    Note: Callable functions must have a function signature
        ``f(ophyd.run_engine.RunEngine)`` and it must return the reason
        for pausing as a string or an empty string to indicate that it should
        not be paused/resumed/killed

    Parameters
    ----------
    pausing_callable : callable
        The condition that must be met for the scan to resume.
        Callable must
    name : str
        The human-readable name of this ScanCondition for logging purposes
    resuming_callable : callable, optional
        A callable that returns True when the scan should resume.
        Defaults to the inverse of the pausing callable
        Function Signature: ``f(ophyd.run_engine.RunEngine)``
    killing_callable : callable, optional
        A callable that returns True if the scan should be killed. Note that
        there is no way to undo a kill command
        Function Signature: ``f(ophyd.run_engine.RunEngine)``
    pause_timeout : float
        time in seconds to wait between checks to see if a scan should be paused
    resume_timeout : float
        time in seconds to wait after pausing a scan to attempt to revive it
    kill_timeout : float
        time in seconds to wait after pausing a scan to kill the scan if it has
        not resumed
    """

    def __init__(self, pausing_callable, name, pause_timeout=.5,
                 resuming_callable=None, resume_timeout=None,
                 killing_callable=None, kill_timeout=None):
        self.pausing_callable = pausing_callable
        # default to the inverse of the pausing callable
        if not resuming_callable:
            resuming_callable = lambda run_engine: (
                "Scan Resuming" if not pausing_callable(run_engine) else "")
        self.resuming_callable = resuming_callable
        self.killing_callable = killing_callable
        self._was_paused = False
        self.name = name
        self.pause_message = ""
        self.killers_note = ""
        self.resume_message = ""
        self.pause_timeout = pause_timeout
        self.resume_timeout = resume_timeout
        self.kill_timeout = kill_timeout
        self.pause_timer = None
        self.resume_timer = None
        self.doomsday_clock = None
        self.continue_checking_for_pause = True

    def stop_checking(self):

        def remove_timer(attr):
            try:
                attr.cancel()
                del attr
            except AttributeError:
                pass

        remove_timer(self.pause_timer)
        remove_timer(self.resume_timer)
        remove_timer(self.doomsday_clock)

        self.continue_checking_for_pause = False

    def __call__(self, run_engine):
        self.continue_checking_for_pause = True
        self.pause_timer = Timer(self.pause_timeout, self._pause, args=[run_engine])
        self.pause_timer.start()
        self.pause_timer.run()

    def __str__(self):
        message = self.name
        if self.pause_message:
            message += ". Paused because {}".format(self.pause_message)
        if self.resume_message:
            message += ". Resumed because {}".format(self.resume_message)
        if self.killers_note:
            message += ". Killed because {}".format(self.killers_note)
        return message

    def __repr__(self):
        return "PauseScanCondition(pausing_callable={}, name={}".format(
            self.pausing_callable, self.name)

    def _kill(self, run_engine):
        """Determine if the scan should be killed

        Parameters
        ----------
        run_engine : ophyd.run_engine.run_engine
            The currently executing run_engine from ophyd
        """
        killers_note = self.killing_callable(run_engine)
        if killers_note:
            # dont bother continuing to check the resume timer
            self.resume_timer.cancel()
            self.killers_note = killers_note
            run_engine.kill(self)
            self._was_paused = False
        else:
            logger.warning("Kill scan clock expired for {} but the "
                           "killing_callable returned False. Restarting"
                           "the doomsday clock".format(self))
            # clear the doomsday finished status and restart it!
            self.doomsday_clock.finished.clear()
            self.doomsday_clock.run()

    def _resume(self, run_engine):
        """Determine if the scan should be resumed

        Parameters
        ----------
        run_engine : ophyd.run_engine.run_engine
            The currently executing run_engine from ophyd
        """
        resume_message = self.resuming_callable(run_engine)
        if resume_message:
            # stop the countdown!
            self.doomsday_clock.cancel()
            # delete the Timer instances
            del self.doomsday_clock
            del self.resume_timer
            # only stash the resume message if it is True
            self.resume_message = resume_message
            run_engine.resume(self)
            self._was_paused = False
            self.pause_message = ""
        else:
            # clear the resume_timer's status and restart it
            self.resume_timer.finished.clear()
            self.resume_timer.run()

    def _pause(self, run_engine):
        """Determine if the scan should be paused

        Parameters
        ----------
        run_engine : ophyd.run_engine.run_engine
            The currently executing run_engine from ophyd
        """
        pause_message = self.pausing_callable(run_engine)
        if pause_message:
            # only stash the pause message if is a non-empty string
            self.pause_message = pause_message
            # clear the old resume message
            self.resume_message = ""
            print("run_engine: %s" % run_engine)
            run_engine.pause(self)
            self._was_paused = True
            # create and start a resume timer
            self.resume_timer = Timer(self.resume_timeout, self._resume,
                                      args=[run_engine])
            self.resume_timer.start()
            self.resume_timer.run()
            # create and start a kill timer if there is a kill_timeout
            # and a killing_callable
            if self.kill_timeout and self.killing_callable:
                self.doomsday_clock = Timer(self.kill_timeout, self._kill,
                                            args=[run_engine])
                self.doomsday_clock.start()
                self.doomsday_clock.run()

        if self.continue_checking_for_pause:
            # clear the pause_timer's status and restart it
            # clear the resume_timer's status and restart it
            self.pause_timer.finished.clear()
            self.pause_timer.run()
