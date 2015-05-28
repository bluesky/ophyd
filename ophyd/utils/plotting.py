import six
from itertools import count
import numpy as np
import matplotlib.pyplot as plt


class PlotManager(object):

    def __init__(self):
        self._has_figures = False
        self._x_name = None  # plot against seq_num

    def setup_plot(self, event_descriptor):
        self.point_counter = count()
        self._has_figures = True
        scalars = []
        images = []
        cubes = []
        for key, val in six.iteritems(event_descriptor['data_keys']):
            print key, val['shape']
            if not val['shape']:
                scalars.append(key)
                continue
            ndim = len(val['shape'])
            if ndim == 2:
                images.append(key)
            elif ndim == 3:
                cubes.append(key)
            else:
                pass  # >3D data just won't be shown

            if self._x_name not in scalars:
                raise NotImplementedError("Not sure how to plot this. Turn "
                                          "of the self's autoplot attribute.")
            scalars.remove(self._x_name)
        self._cube_names = cubes

        # Build figures, axes, lines.
        self._scalar_fig, axes = plt.subplots(len(scalars), sharex=True)
        self._scalar_axes = {name: ax for name, ax in zip(scalars, axes)}
        self._scalar_lines = {name: ax.plot([], [])[0]
                              for name, ax in six.iteritems(self._scalar_axes)}
        for name, ax in six.iteritems(self._scalar_axes):
            ax.set(title=name)
        self._scalar_fig.subplots_adjust()
        self._image_figs = {name: plt.figure() for name in images + cubes}
        self._image_axes = {name: fig.add_axes((0, 0, 1, 1))
                            for name, fig in six.iteritems(self._image_figs)}
        self._img_objs = {}  # will hold AxesImage objects
        self._img_uids = {name: deque() for name in images + cubes}
        show_all_figures()

    def update_plot(self, event):
        if not self._has_figures:
            # setup_plot has not been called; we have to wait.
            return
        # Add a data point to the subplot for each scalar.
        point_num = next(self.point_counter)
        if self._x_name is not None:
            x_val = event['data'][self._x_name]['value']
        else:
            x_val = point_num
        for name, ax in six.iteritems(self._scalar_axes):
            y_val = event['data'][name]['value']
            line = self._scalar_lines[name]
            old_x, old_y = line.get_data()
            x = np.append(old_x, x_val)
            y = np.append(old_y, y_val)
            line.set_data(x, y)
            _refresh_axes(ax)

        # Try to get the latest image, or a recent image,
        # to update each image figure.
        for name, ax in six.iteritems(self._image_axes):
            datum_uid = event['data'][name]['value']
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
                    except filestore.DatumNotFound:
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
        draw_all_figures()


def _refresh_axes(ax):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1)
    ax.relim(visible_only=True)
    ax.autoscale_view(tight=True)


def show_all_figures():
    for f_mgr in plt._pylab_helpers.Gcf.get_all_fig_managers():
        f_mgr.canvas.figure.show()


def draw_all_figures():
    for f_mgr in plt._pylab_helpers.Gcf.get_all_fig_managers():
        f_mgr.canvas.draw()
        f_mgr.canvas.flush_events()
