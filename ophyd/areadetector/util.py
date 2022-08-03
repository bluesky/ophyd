import inspect
import os
import re
import sys
from collections import namedtuple

from ..utils.epics_pvs import records_from_db
from .base import EpicsSignalWithRBV
from .detectors import AreaDetector

StubInfo = namedtuple("StubInfo", ("signal_type", "record"))


def get_prop_name(pv):
    """Get a property name from the camel-case AreaDetector PV name"""
    # If it's all capital letters and underscores, then just convert
    # to lower-case and that's it
    m = re.match("^[A-Z0-9_]+$", pv)
    if m:
        return pv.lower()

    # If the name starts with a bunch of capital letters, use
    # all but the last one as one word
    # e.g., TESTOne -> test_one
    m = re.match("^([A-Z0-9]+)", pv)
    if m:
        start_caps = m.groups()[0]
        pv = pv[len(start_caps) :]
        pv = "".join([start_caps[:-1].lower(), "_", start_caps[-1].lower(), pv])

    # Get all groups of caps or lower-case
    # e.g., AAAbbbCCC -> 'AAA', 'bbb, 'CCC'
    split = re.findall("([a-z0-9:]+|[:A-Z0-9]+)", pv)
    ret = []

    # Put them all back together, removing single-letter splits
    for s in split:
        if ret and len(ret[-1]) == 1:
            ret[-1] += s
        else:
            ret.append(s)

    return "_".join(ret).lower()


def _suffixes_from_device(devcls):
    """Get all suffixes from a device, given its class"""
    for cpt, attr in devcls._sig_attrs.items():
        if hasattr(cpt, "defn"):
            items = [(cls, suffix) for cls, suffix, kwargs in cpt.defn.values()]
        elif hasattr(cpt, "suffix"):
            items = [(cpt.cls, cpt.suffix)]
        else:
            items = []

        for cls, suffix in items:
            yield suffix
            if issubclass(cls, EpicsSignalWithRBV):
                yield "{}_RBV".format(suffix)


def get_stub_info(db_file, macros=None, base_class=AreaDetector):
    """Stub out a new AreaDetector directly from a database file

    Yields lines of code from the generated class definition.

    Parameters
    ----------
    db_file : str
        The database filename to load from
    macros : list, optional
        List of macros to remove, defaults to just $(P)$(R)
    base_class : class
        The base class - required to determine which signals _not_ to add.
        Defaults to AreaDetector
    """
    if not inspect.isclass(base_class):
        raise ValueError(
            "base_class should be a class, got {!r} instead" "".format(base_class)
        )

    if macros is None:
        macros = ("$(P)$(R)",)

    records = [record for rtype, record in records_from_db(db_file)]

    def remove_macros(record):
        for macro in macros:
            record = record.replace(macro, "")
        return record

    records = [remove_macros(record) for record in records]

    # Get all the signals on the base class and remove those from
    # the list.

    base_recs = _suffixes_from_device(base_class)
    records = set(records) - set(base_recs)
    rbv_records = [record for record in records if record.endswith("_RBV")]
    records -= set(rbv_records)
    rbv_only = [
        record for record in rbv_records if record.rsplit("_", 1)[0] not in records
    ]

    records = set(records).union(rbv_only)
    records = list(records)

    for record in sorted(records):
        if record in rbv_only:
            type_ = "ro"
        else:
            rbv_pv = "%s_RBV" % record
            has_rbv = rbv_pv in rbv_records
            if has_rbv:
                type_ = "with_rbv"
            else:
                type_ = "rw"

        yield StubInfo(record=record, signal_type=type_)


def create_detector_stub(
    db_file,
    macros=None,
    base_class=AreaDetector,
    property_name_fcn=None,
    det_name=None,
    cpt_class="C",
    signal_rbv_class="SignalWithRBV",
    signal_rw_class="EpicsSignal",
    signal_ro_class="EpicsSignalRO",
):
    """Stub out a new AreaDetector camera directly from a database file

    Yields lines of code from the generated class definition.

    Parameters
    ----------
    db_file : str
        The database filename to load from
    macros : list, optional
        List of macros to remove, defaults to just $(P)$(R)
    base_class : class
        The base class - required to determine which signals _not_ to add.
        Defaults to AreaDetector
    property_name_fcn : callable, optional
        Function to create property name from a pv. Signature:
            # def name_func(pv):
            #     return 'prop_name'
    det_name : str, optional
        The detector name which will be the class name
        Defaults to DatabaseFilenameDetector
    cpt_class : str
        Component class name to use. Default 'C'
    signal_rbv_class: str
        Class to use when a signal has a separate setpoint/readback.
        Default 'SignalWithRBV'
    signal_rw_class: str
        Class to use when a signal has only a single setpoint/readback PV.
        Default 'EpicsSignal'
    signal_ro_class: str
        Default 'EpicsSignalRO'
        Class to use when only a readback PV exists.
    """

    if det_name is None:
        det_name = os.path.split(db_file)[1]
        det_name = os.path.splitext(det_name)[0]
        det_name = "%sDetectorCam" % det_name

    yield "class {}({}):".format(det_name, base_class.__name__)

    if property_name_fcn is None:
        property_name_fcn = get_prop_name

    yield "    _html_docs = ['']"

    stub_info = get_stub_info(db_file, macros=macros, base_class=base_class)

    class_map = {
        "ro": signal_ro_class,
        "rw": signal_rw_class,
        "with_rbv": signal_rbv_class,
    }

    for info in sorted(stub_info):
        prop_name = property_name_fcn(info.record)
        cls = class_map[info.signal_type]
        info = dict(
            prop_name=prop_name, cpt_class=cpt_class, cls=cls, record=info.record
        )
        yield ("    {prop_name} = {cpt_class}({cls}, {record!r})" "".format(**info))


def stub_templates(path, **kwargs):
    """Stub out a new AreaDetector directly from all database files in a path"""
    for fn in os.listdir(path):
        full_fn = os.path.join(path, fn)
        if fn.endswith(".db") or fn.endswith(".template"):
            yield from create_detector_stub(full_fn, **kwargs)


if __name__ == "__main__":
    stub_templates("/epics/support/areaDetector/1-9-1/ADApp/Db/")
    sys.exit(0)
