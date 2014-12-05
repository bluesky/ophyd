import numpy

from ophyd.runengine import RunEngine

class Scan(object):
    def __init__(self):
        self._run_eng = RunEngine(None)
        self._scan_args = dict()
        self._last_data = None

        self.triggers = None
        self.detectors = None

        self.paths = None
        self.positioners = None

    def generatePathsFromPts(self, dim, start, stop, npts):
        """Generate Paths from start, stop and number of pts
        
        :param dim: Dimensionality of scan (1 = linear)
        :param start: Array of start values.
        :param stop: Array of stop values.
        :param npts: Number of points (1 will be added to create good intervals)
        
        For the Arrays of :param start: and :param stop: these should have a dimension
        (n x m) where n is the number of positioners in each part of the loop and m is
        the dimensionality of the scan.
        """
        

    def checkPaths(self):
        pass

    def preScan(self):
        pass

    def postScan(self):
        pass

    def run(self):
        self.checkPaths()
        self.preScan()

        if self.detectors is None:
            self._scan_args['detectors'] = self._default_detectors
        else:
            self._scan_args['detectors'] = self.detectors

        if self.triggers is None:
            self._scan_args['triggers'] = self.default_triggers
        else:
            self._scan_args['triggers'] = self.triggers


        # Set the paths for the positioners

        for pos,path in zip(self.positioners, self.paths):
            pos.set_tradjectory = path

        self._last_data = self._run_eng.start_run(run_id, 
                                                  scan_args=self._scan_args)

        self.postScan()

    @property
    def data(self):
        """Return the last scanned data set"""
        return self._last_data

    @property
    def default_triggers(self):
        """Return the default triggers for this scan"""
        return self._default_triggers

    @default_triggers.setter
    def default_triggers(self, triggers):
        """Set the default triggers for this scan"""
        self._default_triggers = triggers

    @property
    def default_detectors(self):
        """Return the default detectors for this scan"""
        return self._default_detectors

    @default_detectors.setter
    def default_detectors(self, detectors):
        """Set the default detectors for this scan"""
        self._default_detectors = detectors

class ScanND(Scan):
    """Class for a N-Dimensional Scan"""
    def __init__(self):
        Scan.__init__(self)
    
    def __call__(self, positioners, start, stop, npts,
                 triggers=None, detectors=None)
        self.

class AScan(ScanND):
    
class DScan(AScan):

