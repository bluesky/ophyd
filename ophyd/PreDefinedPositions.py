from bluesky.planstubs import mv
import collections
import time
import networkx as nx
from matplotlib import pyplot as plt
import functools
import operator


class PreDefinedPositions():
    '''
    A class that is used to create a 'collection' of components, and allow a
    series of pre-defined 'locations' to be designated. It allows motion
    between these locations via calculated 'paths'. These 'paths' are
    calculated based on the optional 'neighbours' dictionary, which for each
    'location' defines a list of other locations that it is 'safe' to move
    directly to. The 'components' in the instance can be any 'component' in
    ophyd: such as motor axes, detectors, gate valves, their configuration
    attributes and or even another PreDefinedPositions instance. The
    'locations' do not need to have a value specifed for every component in the
    collection, and the collection can be in more than one 'location' at any
    given time. A further optional dictionary allows the user to define a
    'volume' for all or some 'locations', within which the device is considered
    'in the location'. Moves to/from a location always end at the 'location'
    defined in the 'locations' dictionary. If a 'volume' is not defined for any
    of the 'locations' then it is assumed to be in that location if all listed
    component values are with 1% of the 'location'.

    Parameters
    ----------
    components : Dictionary.
        A dictionary of components associated with this collection, with
        keywords being the name to use in this collection and the value being
        the component. A reference to each component will be created so that
        they can be accessed using 'collection.name' for each component.
        Components can be any components including but not limited too:
        motor axes, detectors, gate valves (and thier configuration attributes)
        or even another PreDefinedPositions 'collection'.
    locations : dictionary, optional.
        A keyword:Value dictionary that lists all of the predefined positions
        (keyword) and a list of axis-value pairs to be set in this location in
        the form: {location1:[axis1,value1,axis2,value2,...],
                   location2:[axis1,value1,axis2,value2,...],.....}.
            .. note::
                #. Not all axes need to have a specifed value for each device
                   location, only those with a specifed value are moved/checked
                   for a given location.
                #. All axes specifed in this dictionary must be specifed as
                   components in 'components'.
    neighbours : Dictionary, optional.
        A keyword:value dictionary where each keyword is a location defined in
        'locations' and each value is a list of 'neighbours' for that location.
        Motion can only occur between neighbours, for non-neighbours a path
        through various locations will be used, if it is found using
        self.find_path. Optionally if the list contains 'All' this indicates
        that evey location is accesible from this one. If no neighbours are
        defined for this location then it is assumed that no direct motion is
        allowed from this location.
    regions : Dictionary, optional.
        The optional keyword:value dictionary that has location keywords and
        'region' values 'region' is a dictionary that has axis_name keywords
        and [min_val, max_val] values denoting the range of values for this
        location and axis. This dictionary has the form:
            {location1:{'axis1_name':[axis1_min_val,axis1_max_val],
                        'axis2_name':[axis2_min_val,axis2_max_val],...},
             location2:{'axis1_name':[axis1_min_val,axis1_max_val],
                        'axis2_name':[axis2_min_val,axis2_max_val],...},
                                          ....}.
            .. note::
                Not all locations in the 'locations' require an entry in this
                dictionary and not all axes defined with a value in 'locations'
                , for a given location, must have a range in this dictionary
                for the given location. For any axis that a 'range' is not
                provided a default range of +/- 1% is used.

    .. note::
        NOTES ON PREDEFINED MOTION WITH NEIGHBOURS:
        #. To ensure the motion to a predefined location always occurs when
           using neighbours to define motion 'paths' it is best to ensure that
           the device is always in a 'location' by making sure that motion can
           not move the device outside of all 'locations'.
        #. To ensure that motion occurs always via a path then each 'point' in
           the path should be a location, and it should only have the
           neighbours that are before or after it in the required path.
    '''
    def __init__(self, components, *, locations={}, neighbours={}, regions={}):

        # Define inputs as attributes
        self.components = components
        self.locations = locations
        self.neighbours = neighbours
        self.regions = regions

        # Define components as attributes
        for attribute in list(components.keys()):
            self.attribute = components[attribute]

        self.nxGraph = nx.DiGraph(directed=True)
        self.nxGraph.add_nodes_from(list(self.locations.keys()))

        for location in list(neighbours.keys()):
            if 'All' in neighbours[location]:
                for neighbour, location in list(self.locations.keys()):
                    self.nxGraph.add_edge(location, neighbour)
            else:
                for neighbour in neighbours[location]:
                    self.nxGraph.add_edge(location, neighbour)

        def mv_plan(to_location):
            '''Returns a plan to move to 'to_location'.

            A function that returns a plan that can move the collection  to the
            location defined by 'to_location'

            Parameters
            ----------
            to_location: string
                The name of the location that it is required to move too.
            '''

            setattr(self, to_location, mv_plan(to_location))
            # This resolves an issue with the definition being set to None
            # after a call
            path_list = self.find_path(from_location='current_location',
                                       to_location=to_location)
            if to_location not in list(self.locations.keys()):
                raise ValueError(f'{to_location} is not a pre defined\
                                 position')
            else:
                for location in path_list:
                    print('Move {} to "{}"'.format(self.name, location))
                    yield from mv(*self.locations['location'])

        for location in self.locations:  # Define the position attributes
            setattr(self, location, mv_plan(location))

    def set(self, value):
        '''Moves the collection to the location defined by 'value' and returns
        a status object.

        This function mimics the 'set' function of an ophyd 'device', it is
        primarily used to allow instances of this class to be added as
        'components' of another instance.

        Parameters
        ----------
        value, string:
            The pre defined location that the object is to move to.

        Returns
        -------
        status, MoveStatus object:
            Returns a MoveStatus object.

        Raises:
        -------
        ValueError:
            On invalid locations.

        '''

        if value not in list(self.locations.keys()):
            raise ValueError(f'{value} is not a pre defined position')
        else:
            status = []
            path_list = self.find_path(from_location='current_location',
                                       to_location=value)

            for location in path_list:
                axis_list = self.locations[location]
                for i in range(0, len(axis_list), 2):
                    status.append(getattr(self, axis_list[i]).
                                  set(axis_list[i+1]))

        return functools.reduce(operator.and_, status)

    def read(self):
        '''
        An attribute that returns the current 'location' of the unit as an
        ordered dictionary. This is used identically to the read attribute
        function for a standard device and therefore can be used in the
        baseline.

        Parameters
        ----------
        read_dict: ordered dictionary, ouput
            The output dictionary that matches the standard output for a
            Device.
        '''

        out_dict = collections.OrderedDict()
        out_dict[self.name+'_location'] = {'timestamp': time.time(),
                                           'value': self.status}

        read_dict = super().read()
        read_dict.update(out_dict)

        return read_dict

    def describe(self):
        '''
        An attribute that returns the current 'location' description of the
        output data as an ordered dictionary. This is used identically to the
        describe attribute function for a standard device and therefore can be
        used in the baseline.

        Parameters
        ----------
        describe_dict: ordered dictionary, ouput
            The output dictionary that matches the standard output for a
            Device.
        '''

        out_dict = collections.OrderedDict()
        out_dict[self.name+'_location'] = {'dtype': 'string',
                                           'lower_ctrl_limit': None,
                                           'precision': None,
                                           'shape': [],
                                           'source': 'None',
                                           'units': None,
                                           'upper_ctrl_limit': None}

        describe_dict = super().describe()
        describe_dict.update(out_dict)

        return describe_dict

    def find_path(self, from_location=None, to_location=None):
        '''Find the shortest path from 'from_location' to 'to_location'.
        Find the shortest path from 'from_location' to 'to_location' passing
        only thorugh the neighbours for each location defiend by the dictionary
        'neighbours'. Returns an empty list if no path found otherwise returns
        a list of 'locations' that define the path. If to_location is None then
        it returns a dictionary showing the shortest path to all possible
        locations. If from_location is None it returns a dictionary showing the
        shortest path from all locations to the current location. If both are
        None it returns a dictioanry of dictionaries. If from_location is
        'current_location' the starting point is changed to the current
        location.

        Parameters
        ---------
        from_location: string
            The name of the starting location required for the path.
        to_location: string
            The name of the ending location required for the path.
        path_list: list, output
            A list locations indicating the path to take to reach the required
            position.
        '''

        if from_location is not 'current_location':
            path_list = nx.shortest_path(self.nxGraph, source=from_location,
                                         target=to_location)
        elif isinstance(self.status_list, str) and self.neighbours is not None:
            path_list = (self.status_list)
        else:
            if self.neighbours is None:
                path_list = [to_location]
            else:
                path_list = []
                for location in self.status_list:
                    prev_path_list = path_list
                    path_list = nx.shortest_path(self.nxGraph, source=location,
                                                 target=to_location)

                    if len(prev_path_list) > 1 and\
                       len(prev_path_list) < len(path_list):
                        path_list = prev_path_list

        return path_list

    def visualize_paths(self, fig_size=[10, 10],
                        axis_labels=['arb. axis', 'arb. axis'],
                        options={}):
        ''' Creates a plot of the possible paths between the predefined
        locations.

        PARAMETERS
        ----------
        fig_size: list, optional
            A list containing the horizontal and vertical size to make the
            figure.
        axis_labels: list, optional
            A list of horizontal and vertical axis names for the figure.
        options: dict, optional
            An optional dictionary that contains kwargs for the draw_networkx
            function from the networkx module.

        '''

        if self.locations is None:
            print('No locations to visualize')
        else:

            default_options = {'pos': nx.circular_layout(self.nxGraph),
                               'node_color': 'darkturquoise',
                               'edge_color': 'grey', 'node_size': 6000,
                               'width': 3, 'arrowstyle': '-|>',
                               'arrow_size': 12}
            default_options.update(options)

            plt.figure('visualize {} paths'.format(self.name),
                       figsize=(fig_size[0], fig_size[1]))
            plt.xlabel(axis_labels[0])
            plt.ylabel(axis_labels[1])
            nx.draw_networkx(self.nxGraph, arrows=True, **default_options)

    @property
    def position(self):
        '''Lists the current locations the collection is in.

        This returns a list containing the names of the current locations that
        the collection is in.

        Returns
        -------
        location_list : list
        '''

        if self.locations is not None:
            location_list = 'unknown location'
            for location in self.locations:
                in_position = True
                for i in range(0, len(self.locations[location]), 2):
                    axis = self.locations[location][i]
                    value = self.locations[location][i+1]

                    if hasattr(getattr(self, axis), 'position'):
                        if isinstance(self.in_band, float):
                            if getattr(self, axis).position <\
                               value - self.in_band or\
                               getattr(self, axis).position >\
                               value + self.in_band:

                                in_position = False
                        else:
                            if getattr(self, axis).position <\
                               self.in_band[location][axis][0] or\
                               getattr(self, axis).position >\
                               self.in_band[location][axis][1]:

                                in_position = False

                    elif hasattr(getattr(self, axis), 'get'):
                        if isinstance(self.in_band, float):
                            if getattr(self, axis).get() <\
                               value - self.in_band or\
                               getattr(self, axis).get() >\
                               value + self.in_band:

                                in_position = False
                        else:
                            if getattr(self, axis).get() <\
                               self.in_band[location][axis][0] or\
                               getattr(self, axis).get() >\
                               self.in_band[location][axis][1]:

                                in_position = False

                    elif hasattr(getattr(self, axis), 'status'):
                        if getattr(self, axis).status is not value:
                            in_position = False

                if in_position:
                    if location_list == 'unknown location':
                        location_list = [location]
                    else:
                        location_list.append(location)
        else:
            location_list = ['no locations']

        return location_list
