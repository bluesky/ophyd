from .plugins import ProcessPlugin


class ProcessPluginOrch(ProcessPlugin):
    def configure_average(self, num_to_avg=1, **kwargs):
        """
        num_to_avg: int

        Configures ProcessPlugin to output
        and average of the last num_to_avg images
        """

        # Most intuitive configuration is
        # set by default. Can be overriden by user with kwargs.
        self.enable_background.put(0)
        self.enable_flat_field.put(0)
        self.enable_offset_scale.put(0)

        self.enable_filter.put(1)
        self.enable.put(1)
        self.filter_type.put(1)  # Average

        self.auto_reset_filter.put(num_to_avg)
        self.filter_callbacks.put(1)  # Array N only
        self.num_filter.put(num_to_avg)

        # Overriding with kwargs part
        properties = {
            kwargs.get("enable_background"): self.enable_background,
            kwargs.get("enable_flat_field"): self.enable_flat_field,
            kwargs.get("enable_offset_scale"): self.enable_offset_scale,
            kwargs.get("enable_filter"): self.enable_filter,
            kwargs.get("enable"): self.enable,
            kwargs.get("filter_type"): self.filter_type,
            kwargs.get("auto_reset_filter"): self.auto_reset_filter,
            kwargs.get("filter_callbacks"): self.filter_callbacks,
            kwargs.get("num_filter"): self.num_filter,
            kwargs.get("reset_filter"): self.reset_filter,
        }

        for _property in properties.keys():
            if _property is not None:
                properties[_property].put(_property)
