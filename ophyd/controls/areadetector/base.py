from __future__ import print_function
import inspect
import re
import sys

from ..ophydobj import OphydObject
from ..signal import (Signal, EpicsSignal)
from . import docs


# TODO: removal of signalgroup, need to move to OphydDevices here
class SignalGroup:
    def __init__(self, *args, **kwargs):
        pass

    def add_signal(self, *args, **kwargs):
        pass


def name_from_pv(pv):
    '''Create a signal's ophyd name based on the PV'''
    name = pv.lower().rstrip(':')
    name = name.replace(':', '.')
    return name


def lookup_doc(cls_, pv):
    '''Lookup documentation extracted from the areadetector html docs

    Go from top-level to base-level class, looking up html documentation
    until we get a hit.

    .. note:: This is only executed once, per class, per property (see ADSignal
        for more information)
    '''
    classes = inspect.getmro(cls_)

    for class_ in classes:
        try:
            html_file = class_._html_docs
        except AttributeError:
            continue

        for fn in html_file:
            try:
                doc = docs.docs[fn]
            except KeyError:
                continue

            try:
                return doc[pv]
            except KeyError:
                pass

            if pv.endswith('_RBV'):
                try:
                    return doc[pv[:-4]]
                except KeyError:
                    pass

    return 'No documentation found [PV suffix=%s]' % pv


class ADBase(OphydObject):
    '''The AreaDetector base class'''

    _html_docs = ['areaDetectorDoc.html']

    @classmethod
    def _all_adsignals(cls_):
        attrs = [(attr, getattr(cls_, attr))
                 for attr in sorted(dir(cls_))]

        return [(attr, obj) for attr, obj in attrs
                if isinstance(obj, ADSignal)]

    @classmethod
    def _update_docstrings(cls_):
        '''Updates docstrings'''
        for prop_name, signal in cls_._all_adsignals():
            signal.update_docstring(cls_)

    def find_signal(self, text, use_re=False,
                    case_sensitive=False, match_fcn=None,
                    f=sys.stdout):
        '''Search through the signals on this detector for the string text

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
            File-like object that the default match function prints to (Defaults
            to sys.stdout)
        '''
        # TODO: Some docstrings change based on the detector type,
        #       showing different options than are available in
        #       the base area detector class (for example). As such,
        #       instead of using the current docstrings, this grabs
        #       them again.
        cls_ = self.__class__

        def default_match(prop_name, signal, doc):
            print('Property: %s' % prop_name)
            if signal.has_rbv:
                print('  Signal: {0} / {0}_RBV'.format(signal.pv, signal.pv))
            else:
                print('  Signal: %s' % (signal.pv))
            print('     Doc: %s' % doc)
            print()

        if match_fcn is None:
            match_fcn = default_match

        if use_re:
            flags = re.MULTILINE
            if not case_sensitive:
                flags |= re.IGNORECASE

            regex = re.compile(text, flags=flags)

        elif not case_sensitive:
            text = text.lower()

        for prop_name, signal in cls_._all_adsignals():
            doc = signal.lookup_doc(cls_)

            if use_re:
                if regex.search(doc):
                    match_fcn(prop_name, signal, doc)
            else:
                if not case_sensitive:
                    if text in doc.lower():
                        match_fcn(prop_name, signal, doc)
                elif text in doc:
                    match_fcn(prop_name, signal, doc)

    @property
    def signals(self):
        '''A dictionary of all signals (or groups) in the object.

        .. note:: Instantiates all lazy signals
        '''
        def safe_getattr(obj, attr):
            try:
                return getattr(obj, attr)
            except:
                return None

        if self.__sig_dict is None:
            attrs = [(attr, safe_getattr(self, attr))
                     for attr in sorted(dir(self))
                     if not attr.startswith('_') and attr != 'signals']

            self.__sig_dict = dict((name, value) for name, value in attrs
                                   if isinstance(value, (Signal, SignalGroup)))

        return self.__sig_dict

    def __init__(self, prefix, **kwargs):
        name = kwargs.get('name', name_from_pv(prefix))

        OphydObject.__init__(self, name=name)

        self._prefix = prefix
        self._ad_signals = {}
        self.__sig_dict = None

    def read(self):
        return self.report()

    @property
    def report(self):
        # TODO: what should this return?
        return {self.name: 0}


class ADSignal(object):
    '''A property-like descriptor

    This descriptor only creates an EpicsSignal instance when it's first
    accessed and not on initialization.

    Optionally, the prefix/suffix can include information from the instance the
    ADSignal is on. On access, the combined prefix and suffix string are
    formatted with str.format().

    Parameters
    ----------
    pv : str
        The suffix portion of the PV.
    has_rbv : bool, optional
        Whether or not a separate readback value pv exists
    doc : str, optional
        Docstring information

    Attributes
    ----------
    pv : str
        The unformatted suffix portion of the PV
    has_rbv : bool, optional
        Whether or not a separate readback value pv exists
    doc : str, optional
        Docstring information

    Examples
    --------

    >>> class SomeDetector(ADBase):
    >>>     signal = ADSignal('Ch{self.channel}', rw=False)
    >>>     enable = ADSignal('enable')
    >>>
    >>>     def __init__(self, prefix, channel=3, **kwargs):
    >>>         super(SomeDetector, self).__init__(prefix, **kwargs)
    >>>         self.channel = channel
    >>>
    >>> test = SomeDetector('my_prefix:')
    >>> print(test.signal)
    EpicsSignal(name='my_prefix.ch3', read_pv='my_prefix:Ch3', rw=False,
                string=False, limits=False, put_complete=False, pv_kw={},
                auto_monitor=None)

    Only at the last line was the signal instantiated. Note how the channel
    information from the object was formatted into the final PV string:
        {prefix}{suffix} -> {prefix}Ch{self.channel} -> my_prefix:Ch3
    '''

    def __init__(self, pv, has_rbv=False, doc=None, **kwargs):
        self.pv = pv
        self.has_rbv = has_rbv
        self.doc = doc
        self.kwargs = kwargs

        self.__doc__ = '[Lazy property for %s]' % pv

    def lookup_doc(self, cls_):
        return lookup_doc(cls_, self.pv)

    def update_docstring(self, cls_):
        if self.doc is None:
            self.__doc__ = self.lookup_doc(cls_)

    def check_exists(self, obj):
        '''Instantiate the signal if necessary'''
        if obj is None:
            # Happens when working on the class and not the object
            return self

        pv = self.pv.format(self=obj)
        try:
            return obj._ad_signals[pv]
        except KeyError:
            base_name = obj.name
            full_name = '%s.%s' % (base_name, name_from_pv(pv))

            read_ = write = ''.join([obj._prefix, pv])

            if self.has_rbv:
                read_ += '_RBV'
            else:
                write = None

            signal = EpicsSignal(read_, write_pv=write,
                                 name=full_name,
                                 **self.kwargs)

            obj._ad_signals[pv] = signal

            if self.doc is not None:
                signal.__doc__ = self.doc
            else:
                signal.__doc__ = self.__doc__

            return obj._ad_signals[pv]

    def __get__(self, obj, objtype=None):
        return self.check_exists(obj)

    def __set__(self, obj, value):
        signal = self.check_exists(obj)
        signal.value = value


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


class NDArrayDriver(ADBase):
    _html_docs = ['areaDetectorDoc.html']

    array_counter = ADSignal('ArrayCounter', has_rbv=True)
    array_rate = ADSignal('ArrayRate_RBV', rw=False)
    asyn_io = ADSignal('AsynIO')

    nd_attributes_file = ADSignal('NDAttributesFile', string=True)
    pool_alloc_buffers = ADSignal('PoolAllocBuffers')
    pool_free_buffers = ADSignal('PoolFreeBuffers')
    pool_max_buffers = ADSignal('PoolMaxBuffers')
    pool_max_mem = ADSignal('PoolMaxMem')
    pool_used_buffers = ADSignal('PoolUsedBuffers')
    pool_used_mem = ADSignal('PoolUsedMem')
    port_name = ADSignal('PortName_RBV', rw=False, string=True)


def update_docstrings(namespace):
    '''Dynamically set docstrings for all ADSignals, based on parsed
    areadetector documentation

    .. note:: called automatically when the module is loaded
    '''
    for var, cls_ in namespace.items():
        if inspect.isclass(cls_) and hasattr(cls_, '_update_docstrings'):
            cls_._update_docstrings()
