{{ fullname | escape | underline}}

.. currentmodule:: {{ module }}

.. autoclass:: {{ objname }}

   {% block components %}
   {% if get_device_info(module, objname) %}
    .. list-table:: Ophyd Device Components
       :header-rows: 1
       :widths: auto

       *  - Attribute
          - Class
          - Suffix
          - Docs
          - Kind
          - Notes
   {% for cpt in get_device_info(module, objname) %}
       *  -  {{ cpt.attr }}
          -  {{ cpt.cls.link }}
          -  {% if cpt.nested_components -%}
                (See below)
             {%- else -%}
                {{ cpt.suffix }}
             {%- endif %}
          -  {{ cpt.doc }}
          -  {{ cpt.kind }}
          -  {% if cpt.inherited_from -%}
            Inherited from {{ cpt.inherited_from.link }}
            {%- endif %}
   {% endfor %}

   {% for ddc in get_device_info(module, objname) %}
   {% if ddc.nested_components %}
    .. list-table:: {{ objname }}.{{ ddc.attr }} Dynamic Device Components
       :header-rows: 1
       :widths: auto

       *  - Attribute
          - Class
          - Suffix
          - Docs
          - Kind
          - Notes
   {% for cpt in ddc.nested_components %}
       *  -  {{ cpt.attr }}
          -  {{ cpt.cls.link }}
          -  {% if cpt.nested_components -%}
                (See below)
             {%- else -%}
                {{ cpt.suffix }}
             {% endif %}
          -  {{ cpt.doc }}
          -  {{ cpt.kind }}
          -  {% if cpt.inherited_from -%}
            Inherited from {{ cpt.inherited_from.link }}
            {%- endif %}
   {% endfor %}
   {% endif %}
   {% endfor %}

   {% endif %}
   {% endblock %}


    {% block methods %}
    {% if methods %}
    .. rubric:: Methods

    .. autosummary::
       :toctree: generated
    {% for item in methods %}
       ~{{ name }}.{{ item }}
    {%- endfor %}
    {% endif %}
    {% endblock %}

    {% block attributes %}
    {% if attributes %}
    .. rubric:: Attributes

    .. autosummary::
    {% for item in attributes %}
       ~{{ name }}.{{ item }}
    {%- endfor %}
    {% endif %}
    {% endblock %}
