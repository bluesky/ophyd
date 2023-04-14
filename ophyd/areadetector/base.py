# type: ignore

import functools
import inspect
import re
import sys
import textwrap
from collections import OrderedDict
from typing import (
    Any,
    Callable,
    ClassVar,
    DefaultDict,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

import networkx as nx
import numpy as np

from ..device import Component, Device, DynamicDeviceComponent
from ..ophydobj import Kind, OphydObject
from ..signal import ArrayAttributeSignal, DerivedSignal, EpicsSignal, EpicsSignalRO
from . import docs


class EpicsSignalWithRBV(EpicsSignal):
    # An EPICS signal that simply uses the areaDetector convention of
    # 'pvname' being the setpoint and 'pvname_RBV' being the read-back

    def __init__(self, prefix, **kwargs):
        super().__init__(prefix + "_RBV", write_pv=prefix, **kwargs)


class NDDerivedSignal(DerivedSignal):
    """
    DerivedSignal to shape a flattened array

    The purpose of this class is to take a flattened array and shape in its
    proper form. The shape of the final array may be static in which case the
    shape and number of dimensions can be set as static integers. Otherwise,
     other signals from this classes parent can inform the proper shape of
    the array.

    Parameters
    ----------
    derived_from : str, ``ophyd.Signal``
        Either a `str` that specifies the attribute of the parent we will get
        the unshaped array or an ``ophyd.Signal`` itself.

    shape: tuple
        A tuple containing integers in the case of a static array or links to
        ``Signal`` objects. The specifications of the signals follows the same
        rules as the ``derived_from`` parameter

    num_dimensions: int, str, ``Signal``, optional
        The number of dimensions of the array. This can either be a static
        ``int`` or a ``Signal`` itself.

    Example
    -------
    .. code:: python

        class TwoDimensionalDetector(Device):

            flat_array = Cpt(EpicsSignal, ':Array')
            width = Cpt(EpicsSignalRO, ':Width')
            height = Cpt(EpicsSignalRO, ':Height')
            shaped_array = Cpt(NDDerivedSignal, 'flat_array',
                                               shape=('height', 'width'),
                                               num_dimensions=2)
    """

    def __init__(
        self, derived_from, *, shape, num_dimensions=None, parent=None, **kwargs
    ):
        # Assemble our shape of signals
        self._shape = []
        self._has_subscribed = False
        for dim in shape:
            if isinstance(dim, str):
                dim = getattr(parent, dim)
            self._shape.append(dim)
        self._shape = tuple(self._shape)
        # Assemble ndims
        if not num_dimensions:
            num_dimensions = len(self._shape)
        if isinstance(num_dimensions, str):
            num_dimensions = getattr(parent, num_dimensions)
        self._num_dimensions = num_dimensions
        super().__init__(derived_from=derived_from, parent=parent, **kwargs)

    @property
    def derived_shape(self):
        """Shape of output signal"""
        shape = list()
        for dim in self._shape:
            if not isinstance(dim, (int, float)):
                dim = dim.get()
            shape.append(dim)
        return tuple(shape)

    @property
    def derived_ndims(self):
        """Number of dimensions"""
        ndims = self._num_dimensions
        if not isinstance(ndims, (int, float)):
            ndims = ndims.get()
        return int(ndims)

    def forward(self, value):
        """Flatten the array to send back to the DerivedSignal"""
        return np.array(value).flatten()

    def inverse(self, value):
        """Shape the flat array to send as a result of ``.get``"""
        array_shape = self.derived_shape[: self.derived_ndims]
        if not any(array_shape):
            raise RuntimeError(f"Invalid array size {self.derived_shape}")

        array_len = np.prod(array_shape)
        if len(value) < array_len:
            raise RuntimeError(
                f"cannot reshape array of size {len(value)} "
                f"into shape {tuple(array_shape)}. Check IOC configuration."
            )

        return np.asarray(value[:array_len]).reshape(array_shape)

    def subscribe(self, callback, event_type=None, run=True):
        cid = super().subscribe(callback, event_type=event_type, run=run)
        if not self._has_subscribed and (
            event_type is None or event_type == self.SUB_VALUE
        ):
            # Ensure callbacks are fired when array is reshaped
            for dim in self._shape + (self._num_dimensions,):
                if not isinstance(dim, int):
                    dim.subscribe(
                        self._array_shape_callback, event_type=self.SUB_VALUE, run=False
                    )
        self._has_subscribed = True
        return cid

    def _array_shape_callback(self, **kwargs):
        # TODO we need a better way to say "latest new is good enough"
        value = self.inverse(self._derived_from._readback)
        self._readback = value
        self._run_subs(sub_type=self.SUB_VALUE, value=value, **self._metadata)


K = TypeVar("K", bound=OphydObject)


class ADComponent(Component[K]):
    #: Default laziness for the component.  All AreaDetector components are
    #: by default lazy - as they contain thousands of PVs that aren't
    #: necesssary for everyday functionality.
    lazy_default: ClassVar[bool] = True

    #: The attribute name of the component.
    attr: Optional[str]
    #: The class to instantiate when the device is created.
    cls: Type[K]
    #: Keyword arguments for the device creation.
    kwargs: Dict[str, Any]
    #: Lazily create components on access.
    lazy: bool
    #: PV or identifier suffix.
    suffix: Optional[str]
    #: Documentation string.
    doc: Optional[str]
    #: Value to send on ``trigger()``
    trigger_value: Optional[Any]
    #: The data acquisition kind.
    kind: Kind
    #: Names of kwarg keys to prepend the device PV prefix to.
    add_prefix: Tuple[str, ...]
    #: Subscription name -> subscriptions marked by decorator.
    _subscriptions: DefaultDict[str, List[Callable]]

    def find_docs(self, parent_class):
        """Find all the documentation related to this class, all the way up the
        MRO"""

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
        """Create a docstring for the component, given the parent class"""

        def make_codeblock(s):
            """Make a codeblock that will render nicely in sphinx"""
            block = [
                "AreaDetector Component",
                "::",
                "",
            ]

            lines = s.split("\n", 1)
            header, lines = lines[0], lines[1:]

            block.append(textwrap.indent(textwrap.dedent(header), prefix=" " * 4))

            lines = "\n".join(lines)
            block.append(textwrap.indent(textwrap.dedent(lines), prefix=" " * 4))
            block.append("")
            return "\n".join(block)

        if self.suffix is None:
            return

        suffixes = [self.suffix]

        if self.suffix.endswith("_RBV"):
            suffixes.append(self.suffix[:-4])

        for doc in self.find_docs(parent_class):
            for suffix in suffixes:
                try:
                    return make_codeblock(doc[suffix])
                except KeyError:
                    pass

        return super().make_docstring(parent_class)


def ad_group(cls, attr_suffix, **kwargs):
    """Definition creation for groups of signals in areadetectors"""
    defn = OrderedDict()
    kwargs.setdefault("lazy", True)
    for attr, suffix in attr_suffix:
        defn[attr] = (cls, suffix, kwargs)
    return defn


def _ddc_helper(signal_class, *items, kind="config", doc=None, **kwargs):
    "DynamicDeviceComponent using one signal class for all components"
    return DynamicDeviceComponent(
        ad_group(signal_class, items, kind=kind, **kwargs),
        doc=doc,
    )


DDC_EpicsSignal = functools.partial(_ddc_helper, EpicsSignal)
DDC_EpicsSignalRO = functools.partial(_ddc_helper, EpicsSignalRO)
DDC_SignalWithRBV = functools.partial(_ddc_helper, EpicsSignalWithRBV)


class ADBase(Device):
    """The AreaDetector base class

    This serves as the base for all detectors and plugins
    """

    _html_docs = ["areaDetectorDoc.html"]
    _default_read_attrs = ()
    _default_configuration_attrs = ()

    def find_signal(
        self, text, use_re=False, case_sensitive=False, match_fcn=None, f=sys.stdout
    ):
        """Search through the signal docs on this detector for the string text

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
        """
        # TODO: Some docstrings change based on the detector type,
        #       showing different options than are available in
        #       the base area detector class (for example). As such,
        #       instead of using the current docstrings, this grabs
        #       them again.

        def default_match(attr, signal, doc):
            print("Property: {}".format(attr), file=f)
            print("  Signal: {!r}".format(signal), file=f)
            print("     Doc: {}".format(doc), file=f)
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
        """Get the plugin which has the given asyn port name

        Parameters
        ----------
        port_name : str
            The port name to search for

        Returns
        -------
        ret : ADBase or None
            Either the requested plugin or None if not found

        """
        try:
            name = self.port_name.get()
        except AttributeError:
            pass
        else:
            if name == port_name:
                return self

        for name, subdevice in self.walk_subdevices(include_lazy=True):
            if hasattr(subdevice, "get_plugin_by_asyn_port"):
                sig = subdevice.get_plugin_by_asyn_port(port_name)
                if sig is not None:
                    return sig
        return None

    def get_asyn_port_dictionary(self):
        """Return port name : component map

        Returns
        -------
        port_map : dict
            Mapping between port_name and ADBase objects
        """
        # uniqueness of port names enforced at IOC layer
        ret = {}
        try:
            ret.update({self.port_name.get(): self})
        except AttributeError:
            pass

        for name, subdevice in self.walk_subdevices(include_lazy=True):
            if hasattr(subdevice, "get_asyn_port_dictionary"):
                ret.update(subdevice.get_asyn_port_dictionary())

        return ret

    def get_asyn_digraph(self):
        """Get the directed graph of the ASYN ports

        Returns
        -------
        G : networkx.DiGraph
            Directed graph of pipelines

        port_map : dict
            Mapping between port_name and ADBase objects
        """
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

    def visualize_asyn_digraph(self, ax=None, *args, **kwargs):
        """This generates a figure showing the current asyn port layout.

        This method generates a plot showing all of the currently enabled
        Areadetector plugin asyn ports and their relationships. The current
        ports and relationships are found using self.get_asyn_digraph.

        Parameters
        ----------
        ax: matplotlib axes
            if None (default) then a new figure is created otherwise it is
            plotted on the specified axes.
        *args, **kwargs : networkx.draw_networkx args and kwargs.
            For the allowed args and kwargs see the `networkx.draw_networkx documentation
            <https://networkx.github.io/documentation/networkx-1.10/reference/generated/networkx.drawing.nx_pylab.draw_networkx.html>`_
        """
        # Importing matplotlib.pyplot here as it is not a dependency except for
        # this method.
        import matplotlib.pyplot as plt

        # Generate the port_map Digraph.
        G, port_map = self.get_asyn_digraph()
        # Create and label the figure if no ax is provided.
        if not ax:
            fig, ax = plt.subplots()
            ax.set_title("AD port map for {}".format(self.name))
            plt.tick_params(
                axis="x", which="both", bottom=False, top=False, labelbottom=False
            )
            plt.tick_params(
                axis="y", which="both", left=False, right=False, labelbottom=False
            )

        nx.draw_networkx(G, ax=ax, *args, **kwargs)

    def validate_asyn_ports(self):
        """Validate that all components of pipeline are known

        Raises
        ------
        RuntimeError
           If there any input ports to known plugins where the source is
           not known to ophyd
        """
        g, port_map = self.get_asyn_digraph()
        g = nx.Graph(g)
        if port_map and nx.number_connected_components(g) != 1:
            missing_plugins = self.missing_plugins()
            raise RuntimeError(
                "The asyn ports {!r} are used by plugins "
                "that ophyd is aware of but the source plugin "
                "is not.  Please reconfigure your device to "
                "include the source plugin or reconfigure "
                "to not use these ports."
                "".format(missing_plugins)
            )

    def missing_plugins(self):
        """Find missing ports"""
        g, port_map = self.get_asyn_digraph()
        ret = []

        for node in g:
            if node not in port_map:
                ret.append(node)

        return ret

    configuration_names = Component(
        ArrayAttributeSignal, attr="_configuration_names", kind="config"
    )

    @property
    def _configuration_names(self):
        return [getattr(self, c).name for c in self.configuration_attrs]

    @property
    def ad_root(self):
        root = self
        while True:
            if not isinstance(root.parent, ADBase):
                return root
            root = root.parent
