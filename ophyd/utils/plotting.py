import matplotlib.pyplot as plt


class PlotManager(object):

    def update_positioners(self, positioners):
        if len(positioners) == 1:
            self._x_name = positioners[0]
        else:
            self._x_name = None  # plot against seq_num

    def setup_plot(event_descriptor):
        scalars = []
        images = []
        cubes = []
        for key, val in six.iteritems(event_descriptor.data_keys):
            if val['shape'] is None:
                scalars.append(key)
                continue
            ndim = len(val['shape'])
            if ndim == 2:
                images.append(key)
            elif ndim == 3:
                cubes.append(key)
            else:
                pass  # >3D data just won't be shown

            if self._x not in scalars:
                raise NotImplementedError("Not sure how to plot this. Turn "
                                          "of the self's autoplot attribute.")
            scalars.remove(self._x)
        self._cube_names = cubes

        # Build figures, axes, lines.
        self._scalar_fig, axes = plt.subplots(len(scalars), sharex=True)
        self._scalar_axes = {name: ax for name, ax in zip(scalars, axes)}
        self._scalar_lines = {name: ax.plot([], [])[0]}
        self._scalar_fig.subplots_adjust()
        for name, ax in six.iteritems(self._scalar_axes):
            ax.set(title=name)
        self._image_figs = {name: plt.figure() for name in in images + cubes}
        self._image_axes = {fig.add_axes((0, 0, 1, 1))
                            for fig in self._image_figs}
        self._img_objs = {}  # will hold AxesImage objects
        self._img_uids = {name: deque() for name in images + cubes}

    def update_plot(event):
        # Add a data point to the subplot for each scalar.
        x_val = event[self._x_name][0]  # unpack value from raw Event
        for name, ax in self._scalar_axes:
            y_val = event[name][0]  # unpack value from raw Event
            line = self._scalar_lines[name]
            old_x, old_y = line.get_data()
            x = np.append(old_x, x_val)
            y = np.append(old_y, y_val)
            line.set_data(x, y)
        self._scalar_fig.canvas.draw()

        # Try to get the latest image, or a recent image,
        # to update each image figure.
        for name, ax in self._image_axes:
            datum_uid = event[name][0]
            img_array = None
            try:
                img_array = retrieve(datum_uid)
            except DoesNotExist:
                # Data may not be readable yet.
                # Try uids in cache, starting with the most recent one.
                uids = self._img_uids[name]
                for i, datum_uid in enumerate(uids):
                    try:
                        img_array = filestore.retrieve(datum_uid)
                    except filestore.DatumNotFound
                        continue
                    else:
                        # To avoid ever showing an image that is older
                        # than we one we just found,
                        # remove all older images from the cache.
                        for _ in len(uids) - i:
                            self.uids.pop()
                        break
                self._img_uids[name].appendleft(datum_uid)

            # No image available? Skip this update.
            if img_array is None:
                continue

            # If this is an image cube, sum along the first axis
            # and display it like an image.
            # TODO: Display volumes for real.
            if name in self._cube_names:
                img_array = img_array.sum(0)

            # Update the image.
            if name not in self._img_objs:
                self._img_obj[name] = ax.imshow(img_array)
            else:
                img_obj.set_array(img_array)
            self._img_figs[name].canvas.draw()
