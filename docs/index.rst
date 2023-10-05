:html_theme.sidebar_secondary.remove:

.. include:: ../README.rst
    :end-before: when included in index.rst

How the documentation is structured
-----------------------------------

The documentation is split into 2 sections:

.. grid:: 1

    .. grid-item-card:: :material-regular:`person;4em`
        :link: user/index
        :link-type: doc

        The User Guide v1 contains documentation on how to install and use ophyd's original v1 API.

        New users should use this API until v2 has stabilized.

.. toctree::
    :hidden:

    user/index
