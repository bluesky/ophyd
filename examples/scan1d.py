from ophyd.runengine import RunEngine

run_eng = RunEngine(None)

''' Assumes detector params (dwell time, etc) have been 
    previously configured.

    Also assumes that ophyd.runengine.RunEngine exists in the 
    IPython namespace.
'''
def scan1d(run_id, detectors=[], triggers=[], motors=[], paths=[], settle_time=None):
    scan_args = {}
    scan_args['detectors'] = detectors
    scan_args['triggers'] = triggers

    #set positioner trajectories if paths[] were provided.
    #otherwise, assume this has been done already.
    for path,motor in zip(paths,motors):
        motor.set_trajectory(path)
    scan_args['positioners'] = motors
    
    scan_args['settle_time'] = settle_time

    run_eng.start_run(run_id, scan_args=scan_args)
