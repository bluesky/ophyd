from __future__ import print_function
import inspect
import re
import sys
from collections import OrderedDict

from ..signal import (EpicsSignal, EpicsSignalRO)
from . import docs
from ..device import (OphydDevice, Component)


class EpicsSignalWithRBV(EpicsSignal):
    # An EPICS signal that simply uses the areaDetector convention of
    # 'pvname' being the setpoint and 'pvname_RBV' being the read-back

    def __init__(self, prefix, **kwargs):
        super().__init__(prefix + '_RBV', write_pv=prefix, rw=True, **kwargs)


class ADComponent(Component):
    def __init__(self, cls, suffix, **kwargs):
        super().__init__(cls, suffix, lazy=True, **kwargs)

    def find_docs(self, parent_class):
        '''Find all the documentation related to this class, all the way up the
        MRO'''

        classes = inspect.getmro(parent_class)
        for class_ in classes:
            try:
                html_file = class_._html_docs
            except AttributeError:
                continue

            for fn in html_file:
                if fn in docs.docs:
                    yield docs.docs[fn]

    def make_docstring(self, parent_class):
        '''Create a docstring for the component, given the parent class'''
        suffixes = [self.suffix]

        if self.suffix.endswith('_RBV'):
            suffixes.append(self.suffix[:-4])

        for doc in self.find_docs(parent_class):
            for suffix in suffixes:
                try:
                    return doc[suffix]
                except KeyError:
                    pass

        return 'No documentation found [suffix={}]'.format(self.suffix)


# TODO: removal of signalgroup, need to move to OphydDevices here
class SignalGroup:
    def __init__(self, *args, **kwargs):
        pass

    def add_signal(self, *args, **kwargs):
        pass


def ad_group(cls, attr_suffix, **kwargs):
    '''Definition creation for groups of signals in areadetectors'''
    defn = OrderedDict()
    for attr, suffix in attr_suffix:
        defn[attr] = (cls, suffix, kwargs)
    return defn


class ADBase(OphydDevice):
    '''The AreaDetector base class

    This serves as the base for all detectors and plugins
    '''

    _html_docs = ['areaDetectorDoc.html']

    array_counter = ADComponent(EpicsSignalWithRBV, 'ArrayCounter')
    array_rate = ADComponent(EpicsSignalRO, 'ArrayRate_RBV')
    asyn_io = ADComponent(EpicsSignal, 'AsynIO')

    nd_attributes_file = ADComponent(EpicsSignal, 'NDAttributesFile',
                                     string=True)
    pool_alloc_buffers = ADComponent(EpicsSignalRO, 'PoolAllocBuffers')
    pool_free_buffers = ADComponent(EpicsSignalRO, 'PoolFreeBuffers')
    pool_max_buffers = ADComponent(EpicsSignalRO, 'PoolMaxBuffers')
    pool_max_mem = ADComponent(EpicsSignalRO, 'PoolMaxMem')
    pool_used_buffers = ADComponent(EpicsSignalRO, 'PoolUsedBuffers')
    pool_used_mem = ADComponent(EpicsSignalRO, 'PoolUsedMem')
    port_name = ADComponent(EpicsSignalRO, 'PortName_RBV', string=True)

    def find_signal(self, text, use_re=False, case_sensitive=False,
                    match_fcn=None, f=sys.stdout):
        '''Search through the signal docs on this detector for the string text

        Parameters
        ----------
        text : str
            Text to find
        use_re : bool, optional
            Use regular expressions
        case_sensitive : bool, optional
            Case sensitive search
        match_fcn : callable, optional
            Function to call when matches are found Defaults to a function that
            prints matches to f
        f : file-like, optional
            File-like object that the default match function prints to
            (Defaults to sys.stdout)
        '''
        # TODO: Some docstrings change based on the detector type,
        #       showing different options than are available in
        #       the base area detector class (for example). As such,
        #       instead of using the current docstrings, this grabs
        #       them again.

        def default_match(attr, signal, doc):
            print('Property: {}'.format(attr), file=f)
            print('  Signal: %s' % (signal.pv), file=f)
            print('     Doc: %s' % doc, file=f)
            print(file=f)

        if match_fcn is None:
            match_fcn = default_match

        if use_re:
            flags = re.MULTILINE
            if not case_sensitive:
                flags |= re.IGNORECASE

            regex = re.compile(text, flags=flags)

        elif not case_sensitive:
            text = text.lower()

        for cpt, attr in self._sig_attrs.items():
            doc = cpt.make_docstring(self.__class__)

            match = False
            if use_re:
                if regex.search(doc):
                    match = True
            else:
                if not case_sensitive:
                    if text in doc.lower():
                        match = True
                elif text in doc:
                    match = True

            if match:
                match_fcn(attr=attr, signal=getattr(self, attr), doc=doc)


def ADSignalGroup(*props, **kwargs):
    def check_exists(self):
        signals = tuple(prop.__get__(self) for prop in props)
        key = tuple(signal.pvname for signal in signals)
        try:
            return self._ad_signals[key]
        except KeyError:
            sg = SignalGroup(**kwargs)
            for signal in signals:
                sg.add_signal(signal)

            self._ad_signals[key] = sg
            return self._ad_signals[key]

    def fget(self):
        return check_exists(self)

    def fset(self, value):
        sg = check_exists(self)
        sg.value = value

    doc = kwargs.pop('doc', '')
    return property(fget, fset, doc=doc)
