:html_theme.sidebar_secondary.remove:

.. include:: ../README.rst
    :end-before: when included in index.rst

How the documentation is structured
-----------------------------------

The documentation is split into 2 sections:

.. grid:: 2

    .. grid-item-card:: :material-regular:`person;4em`
        :link: user_v1/index
        :link-type: doc

        The User Guide v1 contains documentation on how to install and use ophyd's original v1 API.

        New users should use this API until v2 has stabilized.

    .. grid-item-card:: :material-regular:`person_add;4em`
        :link: user_v2/index
        :link-type: doc

        The User Guide v2 contains documentation on how to use ophyd's provisional v2 API.

        Developers may use this to develop v2 Devices against, but the API is subject to change

.. toctree::
    :hidden:

    user_v1/index
    user_v2/index
