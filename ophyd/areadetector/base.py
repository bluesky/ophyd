import textwrap
import inspect
import re
import sys
from collections import OrderedDict
import networkx as nx

from ..signal import EpicsSignal
from . import docs
from ..device import (Device, Component)
from ..signal import (ArrayAttributeSignal)


class EpicsSignalWithRBV(EpicsSignal):
    # An EPICS signal that simply uses the areaDetector convention of
    # 'pvname' being the setpoint and 'pvname_RBV' being the read-back

    def __init__(self, prefix, **kwargs):
        super().__init__(prefix + '_RBV', write_pv=prefix, **kwargs)


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
        def make_codeblock(s):
            '''Make a codeblock that will render nicely in sphinx'''
            block = ['AreaDetector Component',
                     '::',
                     '',
                     ]

            lines = s.split('\n', 1)
            header, lines = lines[0], lines[1:]

            block.append(textwrap.indent(textwrap.dedent(header),
                                         prefix=' ' * 4))

            lines = '\n'.join(lines)
            block.append(textwrap.indent(textwrap.dedent(lines),
                                         prefix=' ' * 4))
            block.append('')
            return '\n'.join(block)

        suffixes = [self.suffix]

        if self.suffix.endswith('_RBV'):
            suffixes.append(self.suffix[:-4])

        for doc in self.find_docs(parent_class):
            for suffix in suffixes:
                try:
                    return make_codeblock(doc[suffix])
                except KeyError:
                    pass

        return super().make_docstring(parent_class)


def ad_group(cls, attr_suffix, **kwargs):
    '''Definition creation for groups of signals in areadetectors'''
    defn = OrderedDict()
    kwargs.setdefault('lazy', True)
    for attr, suffix in attr_suffix:
        defn[attr] = (cls, suffix, kwargs)
    return defn


class ADBase(Device):
    '''The AreaDetector base class

    This serves as the base for all detectors and plugins
    '''

    _html_docs = ['areaDetectorDoc.html']
    _default_read_attrs = ()
    _default_configuration_attrs = ()

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
            print('  Signal: {!r}'.format(signal), file=f)
            print('     Doc: {}'.format(doc), file=f)
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

        for attr, cpt in self._sig_attrs.items():
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

    def stage(self, *args, **kwargs):
        ret = super().stage(*args, **kwargs)
        try:
            self.validate_asyn_ports()
        except RuntimeError as err:
            self.unstage(*args, **kwargs)
            raise err
        return ret

    def get_plugin_by_asyn_port(self, port_name):
        '''Get the plugin which has the given asyn port name

        Parameters
        ----------
        port_name : str
            The port name to search for

        Returns
        -------
        ret : ADBase or None
            Either the requested plugin or None if not found

        '''
        try:
            name = self.port_name.get()
        except AttributeError:
            pass
        else:
            if name == port_name:
                return self

        for nm in self._sub_devices:
            cpt = getattr(self, nm)
            if hasattr(cpt, 'get_plugin_by_asyn_port'):
                sig = cpt.get_plugin_by_asyn_port(port_name)
                if sig is not None:
                    return sig
        return None

    def get_asyn_port_dictionary(self):
        '''Return port name : component map

        Returns
        -------
        port_map : dict
            Mapping between port_name and ADBase objects
        '''
        # uniqueness of port names enforced at IOC layer
        ret = {}
        try:
            ret.update({self.port_name.get(): self})
        except AttributeError:
            pass

        for nm in self._sub_devices:
            sig = getattr(self, nm)
            if hasattr(sig, 'get_asyn_port_dictionary'):
                ret.update(sig.get_asyn_port_dictionary())

        return ret

    def get_asyn_digraph(self):
        '''Get the directed graph of the ASYN ports

        Returns
        -------
        G : networkx.DiGraph
            Directed graph of pipelines

        port_map : dict
            Mapping between port_name and ADBase objects
        '''
        port_map = self.get_asyn_port_dictionary()
        G = nx.DiGraph()
        for out_port, cpt in port_map.items():
            try:
                in_port = cpt.nd_array_port.get()
            except AttributeError:
                # attribute error because we hit a component which is not
                # a plugin, but is the 'base' data source
                G.add_node(out_port)
            else:
                G.add_edge(in_port, out_port)

        return G, port_map

    def validate_asyn_ports(self):
        '''Validate that all components of pipeline are known

        Raises
        ------
        RuntimeError
           If there any input ports to known plugins where the source is
           not known to ophyd
        '''
        g, port_map = self.get_asyn_digraph()
        g = nx.Graph(g)
        if port_map and nx.number_connected_components(g) != 1:
            missing_plugins = self.missing_plugins()
            raise RuntimeError('The asyn ports {!r} are used by plugins '
                               'that ophyd is aware of but the source plugin '
                               'is not.  Please reconfigure your device to '
                               'include the source plugin or reconfigure '
                               'to not use these ports.'
                               ''.format(missing_plugins))

    def missing_plugins(self):
        '''Find missing ports'''
        g, port_map = self.get_asyn_digraph()
        ret = []

        for node in g:
            if node not in port_map:
                ret.append(node)

        return ret

    configuration_names = Component(ArrayAttributeSignal,
                                    attr='_configuration_names')

    @property
    def _configuration_names(self):
        return [getattr(self, c).name
                for c in self.configuration_attrs]

    @property
    def ad_root(self):
        root = self
        while True:
            if not isinstance(root.parent, ADBase):
                return root
            root = root.parent
