import metadatastore.commands as mdscmd


def register_mds(scan):
    """
    Register metadatastore insert_* functions to consume documents from scan.

    Parameters
    ----------
    scan : ophyd.scans.Scan
    """
    scan._register_scan_callback('event', mdscmd.insert_event)
    scan._register_scan_callback('descriptor', mdscmd.insert_event_descriptor)
    scan._register_scan_callback('stop', mdscmd.insert_run_stop)
    # 'start' is a special case -- see below
    scan._register_scan_callback('start', insert_run_start)

def _make_blc():
    return mdscmd.insert_beamline_config({}, time=time.time())

def insert_run_start(doc):
    "Add a beamline config that, for now, only knows the time."
    doc['beamline_config'] = _make_blc()
    mdscmd.insert_run_start(doc)
