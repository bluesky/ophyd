# vi: ts=4 sw=4 sts=4 expandtab
import inspect
import logging
import warnings
from collections import OrderedDict

from .epics_pvs import *  # noqa: F401, F403
from .errors import *  # noqa: F401, F403
from .paths import make_dir_tree, makedirs  # noqa: F401

logger = logging.getLogger(__name__)


def enum(**enums):
    """Create an enum from the keyword arguments"""
    return type("Enum", (object,), enums)


class OrderedDefaultDict(OrderedDict):
    """
    a combination of defaultdict and OrderedDict

    source: http://stackoverflow.com/a/6190500/1221924
    """

    def __init__(self, default_factory=None, *a, **kw):
        if default_factory is not None and not callable(default_factory):
            raise TypeError("first argument must be callable")
        super().__init__(*a, **kw)
        self.default_factory = default_factory

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):
        if self.default_factory is None:
            args = tuple()
        else:
            args = (self.default_factory,)
        return type(self), args, None, None, self.items()

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return type(self)(self.default_factory, self)

    def __deepcopy__(self, memo):
        import copy

        return type(self)(self.default_factory, copy.deepcopy(self.items()))

    def __repr__(self):
        return "%s(%s, %s)" % (
            self.__class__.__name__,
            self.default_factory,
            super().__repr__(),
        )


def doc_annotation_forwarder(base_klass):
    def wrapper(f):
        f_name = getattr(f, "__name__")
        base_func = getattr(base_klass, f_name)
        base_docs = getattr(base_func, "__doc__")
        base_annotation = getattr(base_func, "__annotations__")
        f.__doc__ = base_docs
        f.__annotations__ = base_annotation

        return f

    return wrapper


def _filtered_ip_ns():
    import IPython

    return {
        k: v for k, v in IPython.get_ipython().user_ns.items() if not k.startswith("_")
    }


def instances_from_namespace(classes, *, ns=None):
    """Get instances of `classes` from the user namespace

    Parameters
    ----------
    classes : type, or sequence of types
        Passed directly to isinstance(), only instances of these classes
        will be returned.

    ns : Dict[str, Any], optional
       namespace to pull from, defaults to getting the
    """
    if ns is None:
        ns = _filtered_ip_ns()
    return [val for val in ns.values() if isinstance(val, classes)]


def ducks_from_namespace(attrs, *, ns=None):
    """Get instances that have all of attributes.

    "Ducks" is a reference to "duck-typing." If it looks like a duck....

    Parameters
    ----------
    attr : Union[str, Iterable[str]]
        name of attribute or list of names
    """
    if isinstance(attrs, str):
        attrs = [attrs]
    if ns is None:
        ns = _filtered_ip_ns()
    return [val for val in ns.values() if all(hasattr(val, attr) for attr in attrs)]


def underscores_to_camel_case(underscores):
    "Convert abc_def_ghi to abcDefGhi"
    if "_" in underscores and underscores.strip("_") != "":
        return "".join(s.capitalize() for s in underscores.split("_"))

    return underscores.capitalize()


def getattrs(obj, gen):
    "For each item in the generator `gen`, yields (attr, getattr(obj, attr))"
    for attr in gen:
        yield attr, getattr(obj, attr)


class DO_NOT_USE:
    "sentinel value"
    ...


def adapt_old_callback_signature(callback):
    """
    If callback has signature callback(), wrap in signature callback(status).

    Parameters
    ----------
    callback: callable
        Expected signature ``callback(status)`` or ``callback()``

    Returns
    -------
    callback: callable
        Signature ``callback(status)``
    """
    # Handle callback with signature callback() for back-compat.
    sig = inspect.signature(callback)
    try:
        # Does this callback accept one positional argument?
        sig.bind(None)
    except TypeError:
        warnings.warn(
            "The signature of a Status callback is now expected to "
            "be cb(status). The signature cb() is "
            "supported, but support will be removed in a future release "
            "of ophyd.",
            DeprecationWarning,
            stacklevel=3,
        )
        raw_callback = callback

        def callback(status):
            # Do nothing with status because the user-provided callback cannot
            # accept it.
            raw_callback()

    return callback
