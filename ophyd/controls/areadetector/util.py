import inspect
import os
import sys
import re

from ...utils.epics_pvs import records_from_db
from .detectors import AreaDetector


def create_detector_stub(db_file, macros=None,
                         base_class=AreaDetector,
                         property_name_fcn=None,
                         det_name=None):

    '''Stub out a new AreaDetector directly from a database file'''

    if not inspect.isclass(base_class):
        raise ValueError('base_class should be a class, got {!r} instead'
                         ''.format(base_class))

    if macros is None:
        macros = ("$(P)$(R)", )

    records = [record for rtype, record in records_from_db(db_file)]

    def remove_macros(record):
        for macro in macros:
            record = record.replace(macro, '')
        return record

    records = [remove_macros(record) for record in records]

    # Get all the signals on the base class and remove those from
    # the list.
    base_signals = base_class._all_adsignals()
    base_recs = [sig.pv for sig in base_signals]
    base_recs.extend(['%s_RBV' % sig.pv for sig in base_signals
                      if sig.has_rbv])

    records = set(records) - set(base_recs)
    rbv_records = [record for record in records
                   if record.endswith('_RBV')]
    records -= set(rbv_records)
    rbv_only = [record
                for record in rbv_records
                if record.rsplit('_')[0] not in records]

    records = set(records).union(rbv_only)
    records = list(records)

    if det_name is None:
        det_name = os.path.split(db_file)[1]
        det_name = os.path.splitext(det_name)[0]
        det_name = '%sDetector' % det_name

    print('class %s(%s):' % (det_name, base_class.__name__))

    def get_prop_name(pv):
        '''Get a property name from the camel-case AreaDetector PV name'''
        # If the name starts with a bunch of capital letters, use
        # all but the last one as one word
        # e.g., TESTOne -> test_one
        m = re.match('^([A-Z0-9]+)', pv)
        if m:
            start_caps = m.groups()[0]
            pv = pv[len(start_caps):]
            pv = ''.join([start_caps[:-1].lower(), '_', start_caps[-1].lower(), pv])

        # Get all groups of caps or lower-case
        # e.g., AAAbbbCCC -> 'AAA', 'bbb, 'CCC'
        split = re.findall('([a-z0-9:]+|[:A-Z0-9]+)', pv)
        ret = []

        # Put them all back together, removing single-letter splits
        for s in split:
            if ret and len(ret[-1]) == 1:
                ret[-1] += s
            else:
                ret.append(s)

        return '_'.join(ret).lower()

    if property_name_fcn is None:
        property_name_fcn = get_prop_name

    print("    _html_docs = ['']")
    for record in sorted(records):
        prop_name = property_name_fcn(record)

        print("    {} = ADSignal('{}'".format(prop_name, record), end='')
        if record in rbv_only:
            # Readback only
            print(", rw=False)")
        else:
            rbv_pv = '%s_RBV' % record
            has_rbv = rbv_pv in rbv_records
            if has_rbv:
                print(", has_rbv=True)")
            else:
                print(")")


def stub_templates(path):
    for fn in os.listdir(path):
        full_fn = os.path.join(path, fn)
        if fn.endswith('.db') or fn.endswith('.template'):
            create_detector_stub(full_fn)


if __name__ == '__main__':
    stub_templates('/epics/support/areaDetector/1-9-1/ADApp/Db/')
    sys.exit(0)
