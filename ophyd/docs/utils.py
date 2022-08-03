import inspect
import os.path
import textwrap
from typing import Dict, List, Type

import ophyd

OPHYD_SKIP = {
    # Methods
    # 'check_value',
    "clear_sub",
    # 'configure',
    # 'describe',
    # 'describe_configuration',
    "destroy",
    # 'get',
    "get_device_tuple",
    "get_instantiated_signals",
    "pause",
    "put",  # prefer `set`
    # 'read',
    # 'read_configuration',
    "resume",
    # 'stage',
    # 'stop',
    # 'subscribe',
    # 'summary',
    # 'trigger',
    # 'unstage',
    "unsubscribe",
    "unsubscribe_all",
    "wait_for_connection",
    "walk_components",
    "walk_signals",
    "walk_subdevice_classes",
    "walk_subdevices",
    # Attributes
    "SUB_ACQ_DONE",
    "SUB_DONE",
    "SUB_READBACK",
    "SUB_START",
    "SUB_VALUE",
    "attr_name",
    "component_names",
    # 'configuration_attrs',
    # 'connected',
    "dotted_name",
    "event_types",
    # 'hints',
    # 'kind',
    "lazy_wait_for_connection",
    # 'lightpath_cpts',
    "name",
    "parent",
    "read_attrs",
    "removed",
    "report",
    "root",
    "signal_names",
    "trigger_signals",
}


short_component_names = {
    ophyd.Component: "",
    ophyd.DynamicDeviceComponent: "DDC",
    ophyd.FormattedComponent: "FCpt",
    # NOTE: Users may add in their own component types here, without
    # re-implementing these documentation helpers
}


def get_class_info(cls: type) -> Dict[str, str]:
    """
    Get class information in a jinja-friendly way.

    Keys for usage include ``name`` (the class name), ``full_name`` (a
    fully-qualified module and class name), ``class`` (the class type itself),
    ``link`` (a link to the class, only showing its name), and ``full_link`` (a
    full link showing the fully-qualified name).

    Parameters
    ----------
    cls : type
        Class type.
    """
    if cls is None:
        return None

    def link_as(text):
        return f":class:`{text} <{full_name}>`"

    full_name = f"{cls.__module__}.{cls.__name__}"
    return {
        "name": cls.__name__,
        "full_name": full_name,
        "class": cls,
        "full_link": f":class:`{full_name}`",
        "link": f":class:`~{full_name}`",
        "link_as": link_as,
    }


def _dynamic_device_component_to_row(base_attrs, cls, attr, cpt):
    """
    Convert an :class:`ophyd.DynamicDeviceComponent` to a table row dictionary.

    Parameters
    ----------
    base_attrs : dict
        Dictionary indicating where base attributes came from.

    cls : ophyd.Device subclass
        The parent class.

    attr : str
        The component attribute name.

    cpt : ophyd.DynamicDeviceComponent
        The component.
    """
    cpt_type = short_component_names.get(type(cpt), type(cpt).__name__)

    doc = cpt.doc or ""
    if doc.startswith(f"{cpt.__class__.__name__} attribute"):
        doc = ""

    nested_components = [
        _component_to_row(base_attrs, cls, attr, dynamic_cpt)
        for attr, dynamic_cpt in cpt.components.items()
    ]

    return dict(
        component=cpt,
        attr=attr if not cpt_type else f"{attr} ({cpt_type})",
        cls=get_class_info(getattr(cpt, "cls", None)),
        nested_components=nested_components,
        doc=doc,
        kind=cpt.kind.name,
        inherited_from=get_class_info(base_attrs.get(attr, None)),
    )


def _component_to_row(base_attrs, cls, attr, cpt):
    """
    Convert an :class:`ophyd.Component` to a table row dictionary.

    Parameters
    ----------
    base_attrs : dict
        Dictionary indicating where base attributes came from.

    cls : ophyd.Device subclass
        The parent class.

    attr : str
        The component attribute name.

    cpt : ophyd.Component
        The component.
    """
    if isinstance(cpt, ophyd.DynamicDeviceComponent):
        return _dynamic_device_component_to_row(base_attrs, cls, attr, cpt)

    cpt_type = short_component_names.get(type(cpt), type(cpt).__name__)

    doc = cpt.doc or ""
    if doc.startswith(f"{cpt.__class__.__name__} attribute"):
        doc = ""

    if doc.startswith("AreaDetector Component") and "::" in doc:
        _, doc = doc.split("::", 1)
        doc = textwrap.dedent(doc).strip()

    return dict(
        component=cpt,  # access to the component instance itself
        attr=attr if not cpt_type else f"{attr} ({cpt_type})",
        cls=get_class_info(getattr(cpt, "cls", None)),
        suffix=f"``{cpt.suffix}``" if cpt.suffix else "",
        doc=doc,
        kind=cpt.kind.name,
        inherited_from=get_class_info(base_attrs.get(attr, None)),
    )


def _get_base_attrs(cls: Type[ophyd.Device]) -> Dict[str, Type[ophyd.Device]]:
    """
    Determine which components came from which base class.

    Parameters
    ----------
    cls : ophyd.Device subclass
    """
    base_devices = [
        base for base in reversed(cls.__bases__) if hasattr(base, "_sig_attrs")
    ]

    return {
        attr: base for base in base_devices for attr, cpt in base._sig_attrs.items()
    }


# NOTE: can't use functools.lru_cache here as it's not picklable
# (or at least this was the case when embedded in conf.py)
_device_cache = {}


def _get_device_info(cls: Type[ophyd.Device]) -> List[Dict]:
    """
    Get Device information that can easily be rendered as a table.

    Parameters
    ----------
    cls : ophyd.Device subclass
    """
    if not issubclass(cls, ophyd.Device):
        return []

    base_attrs = _get_base_attrs(cls)

    return [
        _component_to_row(base_attrs, cls, attr, cpt)
        for attr, cpt in cls._sig_attrs.items()
    ]


def get_device_info(module, name):
    """
    Get Device information that can easily be rendered as a table.

    This is the hook the jinja ``class.rst`` templates use.

    Parameters
    ----------
    module : str
        Module name.

    name : str
        Class name.
    """
    class_name = f"{module}.{name}"
    if class_name not in _device_cache:
        module_name, class_name = class_name.rsplit(".", 1)
        module = __import__(module_name, globals(), locals(), [class_name])
        cls = getattr(module, class_name)
        _device_cache[class_name] = _get_device_info(cls)
    return _device_cache[class_name]


def skip_components_and_ophyd_stuff(app, what, name, obj, skip, options):
    """
    Skip components, leaving only the table information.

    Also, filter out unimportant attributes based on ``OPHYD_SKIP``.
    """
    if isinstance(obj, ophyd.Component):
        return True

    if name.startswith("_"):
        # It's unclear if I broke this or if it's always been broken,
        # but for our use case we never want to document `_` items with
        # autoclass.
        return True

    if name in OPHYD_SKIP:
        return True

    return skip


def rst_with_jinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.

    Usage
    -----

    .. code::

        def setup(app):
            app.connect("source-read", rst_with_jinja)
    """
    # Borrowed from
    # https://www.ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/

    # Make sure we're outputting HTML
    if app.builder.format == "html":
        rendered = app.builder.templates.render_string(
            source[0], app.config.html_context
        )
        source[0] = rendered


def setup(app):
    """
    Setup method to configure caproto sphinx documentation helpers.

    This is a convenience method; advanced users may wish to replicate this
    method on their own.

    Parameters
    ----------
    app : sphinx.Application

    """
    app.connect("autodoc-skip-member", skip_components_and_ophyd_stuff)
    app.connect("source-read", rst_with_jinja)


# The following are convenient defaults that users may import in their
# conf.py:
autosummary_context = {
    # Allow autosummary/class.rst to do its magic:
    "get_device_info": get_device_info,
    "inspect": inspect,
    "path": os.path,
    # Where is your project root, relative to conf.py?
    "project_root": "..",
    # To change where generated source files go, change the following in
    # conf.py:
    "generated_toctree": "generated",
}

autodoc_default_options = {
    "members": "",
    "member-order": "bysource",
    "special-members": "",
    "undoc-members": False,
    "exclude-members": "",
}
autoclass_content = "init"  # otherwise duplicates will be generated

intersphinx_mapping = {
    "ophyd": ("https://blueskyproject.io/ophyd", None),
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://docs.scipy.org/doc/numpy", None),
}
