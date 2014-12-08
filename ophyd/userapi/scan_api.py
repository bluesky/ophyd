from __future__ import print_function
import numpy as np
from time import sleep

from ophyd.runengine import RunEngine

__all__ = ['AScan', 'DScan']

def ensure_iterator(i):
    """Check if i is an iterator. If not return length-1 iterator"""
    if hasattr(i, "__iter__"):
        return i
    else:
        return [i]


class Scan(object):
    def __init__(self):
        self._run_eng = RunEngine(None)
        self._last_data = None

        self.triggers = None
        self.detectors = None
        self._default_detectors = None
        self._default_triggers = None
        self.settle_time = None

        self.paths = list()
        self.positioners = list()

        self._run_id = 0

    def checkPaths(self):
        pass

    def __enter__(self):
        self.preScan()

    def __exit__(self, exec_type, exec_value, traceback):
        self.postScan()
        # Here we can raise the exceptions
        return False

    def preScan(self):
        pass

    def postScan(self):
        pass

    def run(self):
        """Run the scan"""

        self.checkPaths()

        with self:
            self.setupDetectors()
            self.setupTriggers()

            for pos, path in zip(self.positioners, self.paths):
                pos.set_trajectory(path)

            scan_args['detectors']   = self.detectors
            scan_args['triggers']    = self.triggers
            scan_args['positioners'] = self.positioners
            scan_args['settle_time'] = self.settle_time

            # Run the scan!

            self.data = self._run_eng.start_run(self._run_id + 1,
                                                scan_args=scan_args)

    @property
    def run_id(self):
        """Return the last run 'ID'"""
        return self._run_id

    @property
    def data(self):
        """Return the last scanned data set"""
        return self._last_data

    @data.setter
    def data(self, data):
        self._last_data = data

    @property
    def triggers(self):
        """Return the default triggers for this scan"""
        if self._triggers is None:
            return self._default_triggers
        else:
            return self._triggers + self.default_triggers

    @triggers.setter
    def triggers(self, triggers):
        """Set the default triggers for this scan"""
        self._triggers = triggers

    @property
    def detectors(self):
        """Return the default detectors for this scan"""
        if self._detectors is None:
            return self._default_detectors
        else:
            return self._detectors + self.default_detectors

    @detectors.setter
    def detectors(self, detectors):
        """Set the default detectors for this scan"""
        self._detectors = detectors

    @property
    def default_positioners(self):
        """Get the defualt positioners"""
        return self._default_positioners

    @default_positioners.setter
    def default_positioners(self, pos):
        """Set the default positioners"""
        self._default_positioners = pos

    @property
    def default_triggers(self):
        """Get the defualt triggers"""
        return self._default_triggers

    @default_triggers.setter
    def default_triggers(self, trig):
        """Set the default triggers"""
        self._default_triggers = trig

    @property
    def positioners(self):
        """Get the posiitoners for the scan"""
        return self._positioners

    @positioners.setter
    def positioners(self, positioners):
        """Set the positioners for the scan"""
        self._positioners = positioners

    @property
    def paths(self):
        """Get the paths for the scan"""
        return self._paths

    @paths.setter
    def paths(self, paths):
        """Set the paths for the scan"""
        self._paths = paths


class ScanND(Scan):
    """Class for a N-Dimensional Scan"""
    def __init__(self):
        Scan.__init__(self)
        self.dimension = None

    def calcLinearPath(start, stop, npts):
        """Return a linearaly spaced path"""
        return np.linspace(start, stop, npts)

    def calculatePaths(self, start, stop, npts, dim):
        """Calculate a single path given start, stop and npts for dim"""
        N = np.asarray(npts)
        a = self.calcLinearPath(start, stop, npts[dim])
        x = N[::-1][:len(N)-dim-1]
        y = N[:dim]
        a = np.repeat(a, x.prod())
        a = np.tile(a, y.prod())
        return a

    def __call__(self, positioners, start, stop, npts):
        """Run Scan"""

        # This is an n-dimensional scan. We take the dims from
        # the length of npts.

        npts = ensure_iterator(npts)
        dimension = len(npts)
        pos = list()
        paths = list()

        npts = np.asarray(npts) + 1

        start = ensure_iterator(start)
        stop = ensure_iterator(stop)

        for b,e,d in zip(start, stop, range(dimension)):
            # For each dimension we work out the paths
            iter_pos = ensure_iterator(pos[d])
            for p in iter_pos:
                pos.append(p)
                paths.append(self.calcLinearPath(b, e, npts, d))

        self.positioners = pos
        self.paths = paths

        self.run()


class AScan(ScanND):
    def preScan(self):
        ScanND.preScan(self)



class DScan(AScan):
    def __init__(self):
        AScan.__init__(self)

    def preScan(self):
        """Prescan Compute Paths"""
        self._start_positions = [p.position for p in self.positioners]
        self.paths = [np.array(path) + start
                      for path, start in zip(self.paths, self._start_positions)]
        AScan.preScan(self)

    def postScan(self):
        """Post Scan Move to start positions"""
        AScan.postScan(self)
        for pos, start in zip(self.positioners, self._start_positions):
            pos.move(start, wait=True)

        print("\nMoving positioners back to start positions.")
        while any([p.moving for p in self.positioners]):
            sleep(0.1)
        print("Done.")
