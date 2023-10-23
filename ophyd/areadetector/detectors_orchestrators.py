from .detectors import SimDetector


class SimDetectorOrch(SimDetector):
    def configure_peaks(self, **kwargs):
        """
        Grid: dict {"Start": (M,N), "Width": (J,K), "Num": (W,L),
                    "Step": (P,Q)}

        Configures the driver to create a grid of Peaks.
        """

        grid = kwargs.get("grid")

        # Most intuitive configuration is set
        # using grid.
        if grid is not None:
            start_tuple = grid["Start"]
            width_tuple = grid["Width"]
            num_tuple = grid["Num"]
            step_tuple = grid["Step"]

            self.cam.peak_start.put(start_tuple)
            self.cam.peak_width.put(width_tuple)
            self.cam.peak_num.put(num_tuple)
            self.cam.peak_step.put(step_tuple)

        # Making it possible to oberride other parameters that
        # are not basically necessary but influence on the
        # configuration
        properties = {
            kwargs.get("variation"): self.cam.peak_variation,
            kwargs.get("gain"): self.cam.gain,
            kwargs.get("gain_xy"): self.cam.gain_xy,
        }

        for _property in properties.keys():
            if _property is not None:
                properties[_property].put(_property)

        self.cam.sim_mode.put(1)
