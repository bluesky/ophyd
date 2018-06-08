from ophyd import EpicsMotor,Device
import collections
import time
import networkx as nx
from matplotlib.patches import ArrowStyle



class PreDefinedPositions(Device):
    '''
    A class that is used to create a diagnostic unit and/or a single axis mask units. The
    class has the axis as an attribute as well as a series of pre-defined 'locations'. It also 
    allows motion between these locations via 'paths' defined by the optional keyword dictionary
    neighbours. If neighbours is not none it will define the shortest path between the current 
    location and the requested location moving only from a location to it's 'neighbours'.
    
    Parameters
    ----------
    self : numerous paramters
        All of the parameters associated with the parent class 'Device'
    locations : dictionary, optional
        A keyword:Value dictionary that lists all of the predefined locations (keyword) and a 
        list of axis-value pairs to be set in this location in the form: 
        {location1:['axis1_name',value1,axis2_name',value2,...], 
            location2:['axis1_name',value1,axis2_name',value2,...],.....}.
            NOTE: Not all axes need to have a specifed value for each device location, only 
            those with a specifed value are moved/checked for a given location. 
    neighbours : Dictionary, optional
        A keyword:value dictionary where each keyword is a location defined in 'locations' and 
        each value is a list of 'neighbours' for that location. When defined motion occurs only 
        between neighbours, for non-neighbours a path through various locations will be used, if 
        it is found using self.find_path. 
    in_band : float or dictionary, optional
        A float that gives the in-band range for all axes when deciding if the device is 'in' the 
        correct location or not. The default value is 0.1. The optional keyword:value dictionary 
        that lists all of the predefined locations (keyword) and a sub-dictionary that has axis_name
        keywords and [min_val,max_val] values denoting the range of values for this location and 
        axis. This dictionary has the form: 
            {location1:{'axis1_name':[axis1_min_val,axis1_max_val],
                                                   'axis2_name':[axis2_min_val,axis2_max_val],...}, 
            location2:{'axis1_name':[axis1_min_val,axis1_max_val],
                                                   'axis2_name':[axis2_min_val,axis2_max_val],...},
                                          ....}.
            NOTE: All axes defined with a value in 'locations', for a given location, must have a 
            range in this dictionary for the given location, unless the 'value' in location is a 
            string.
    cam_list : list, optional
        A list of cameras associated with this device, they will be accesible via the attribute
        cam or cam1,cam2 etc.
    qem_list : list, optional
        A list of qem's associated with this device, they will be accesible via the attribute
        qem or qem1,qem2 etc.
    gv_list : list, optional
        A list of gv's associated with this device, they will be accesible via the attribute
        gv or gv1,gv2 etc.
    vis_path_options : dict, optional
        A dictionary that allows for different path visulatiztion options, the parameters and values
        are those defined for drawing in the python networkX Module. A set of defaults is used if this 
        parameter is None. May also contain the optional 'axis_labels':['x_label','y_label'] and 
        'fig_size':[x_size,y_size] values.
    NOTES ON PREDEFINED MOTION WITH NEIGHBOURS:
    1. The locations dictionary can include gate valves and/or parameter sets as axes with the 
        value being 'string'.
    2. To ensure the motion to a predefined location always occurs when using neighbours to define
        motion 'paths' it is best to ensure that the device is always in a 'location' by making sure
        that motion can not move the device outside of all 'locations'.
    3. Devices can be in more than one location at a time.
    4. To ensure that motion occurs always via a path then each 'point' in the path should be a 
        location, and it should only have the neighbours that are before or after it in the required
        path.
    '''
    def __init__(self, *args, locations=None, neighbours=None,in_band=0.1, cam_list=None, 
            qem_list=None, gv_list=None, vis_path_options=None,**kwargs):
        super().__init__(*args, **kwargs)

        self.locations = locations
        self.in_band = in_band
        self.neighbours = neighbours
        self.vis_path_options=vis_path_options

        self.nxGraph=nx.DiGraph(directed=True)
        
        if locations is not None: self.nxGraph.add_nodes_from(list(locations.keys()))

        if neighbours is not None:
            for key in neighbours.keys():
                for neighbour in neighbours[key]:
                    self.nxGraph.add_edge(str(key),neighbour)
        elif locations is not None:
            for location in locations.keys():
                for location2 in locations.keys():
                    if location is not location2:
                        self.nxGraph.add_edge(str(location),str(location2))


        if isinstance(cam_list,list): 
            if len(cam_list)==1:
                self.cam=cam_list[0]
            else:
                for i,cam in enumerate(cam_list):
                    setattr(self,'cam{}'.format(i+1),cam_list[i])                

        if isinstance(qem_list,list): 
            if len(qem_list)==1:
                self.qem=qem_list[0]
            else:
                for i,qem in enumerate(qem_list):
                    setattr(self,'qem{}'.format(i+1),qem_list[i])  

        if isinstance(gv_list,list): 
            if len(gv_list)==1:
                self.gv=gv_list[0]
            else:
                for i,gv in enumerate(gv_list):
                    setattr(self,'qem{}'.format(i+1),gv_list[i])  



        def mv_axis(to_location):
            '''
            A function that moves the diagnostic or single axis slit to the location defined by 
            'value'
    
            Parameters
            ----------
            to_location: string
                The name of the location that it is required to move too.
            '''
            
            setattr(self,to_location,mv_axis(to_location))#this resolves an issue with the definition
                                                          #being set to None after a call 
            
            path_list = self.find_path(from_location='current_location',to_location=to_location)
            if path_list == 'unknown location':#if the current location is unknown
                print ('current location is not pre-defined, move to predefined position first')
                print ('a list of locations and axis values can be found using the "locations"')
                print ('attribute, e.g. device.locations')
            else:
                for location in path_list:
                    print ('Move {} to "{}"'.format(self.name,location))
                    axis_value_list=self.get_axis_value_list(location)
                    yield from mv(*axis_value_list)
                    

        if locations is not None:
            for location in self.locations:#define the position attributes
                setattr(self,location,mv_axis(location))

        
        
    def read(self):
        '''
        An attribute that returns the current 'location' of the unit as an ordered dictionary. This
        is used identically to the read attribute function for a standard device and therefore can 
        be used in the baseline.
        
        Parameters
        ----------
        read_dict: ordered dictionary, ouput
            The output dictionary that matches the standard output for a Device.
        '''

        out_dict = collections.OrderedDict()
        out_dict[self.name+'_location'] = {'timestamp':time.time(),'value':self.status }

        read_dict = super().read()
        read_dict.update(out_dict)
        
        return read_dict

    
    
    def describe(self):
        '''
        An attribute that returns the current 'location'description of the output data as an 
        ordered dictionary. This is used identically to the describe attribute function for a 
        standard device and therefore can be used in the baseline.
        
        Parameters
        ----------
        describe_dict: ordered dictionary, ouput
            The output dictionary that matches the standard output for a Device.
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



    def get_axis_value_list(self,location):
        '''
        Returns the axis-value list for a defined location
        
        Returns
        -------
        axis_value_list : list, output
            the axis-value list for the inputted location that is returned
        '''
        axis_value_list=[]
        for item in self.locations[location]:
                if isinstance(item,str):
                    axis_value_list.append(getattr(self,item))
                else:
                    axis_value_list.append(item)
                    
        return axis_value_list
        

    def find_path(self,from_location=None,to_location=None):
        '''
        Find the shortest path from the 'from_location' to 'to_location' passing only thorugh the 
        neighbours for each location defiend by the dictionary 'neighbours'. Returns an empty list 
        if no path found otherwise returns a list of 'locations' that define the path. If to_location 
        is None then it returns a dictionary showing the shortest path to all possible locations. If
        from_location is None it returns a dictionary showing the shortest path from all locations to
        the current location. If both are None it returns a dictioanry of dictionaries. If 
        from_location is 'current_location' the starting point is changed to the current location.
        Parameters
        ---------
        from_location: string
            The name of the starting location required for the path.
        to_location: string
            The name of the ending location required for the path.
        path_list: list, output
            A list locations indicating the path to take to reach the required position.
        '''


        if from_location is not 'current_location':
            path_list = nx.shortest_path(self.nxGraph,source=from_location,target=to_location)
        elif isinstance(self.status_list,str) and self.neighbours is not None:
            path_list=(self.status_list)
        else:
            if self.neighbours is None:
                path_list=[to_location]
            else:
                path_list=[]
                for location in self.status_list:
                    prev_path_list=path_list
                    path_list=nx.shortest_path(self.nxGraph,source=location,target=to_location)

                    if len(prev_path_list)>1 and len(prev_path_len)<len(path_list):
                        path_list=prev_path_list

        return path_list

    @property
    def visualize_paths(self):
        ''' Creates a plot of the possible paths between the predefined locations.
        '''
        if self.locations is None:
            print ('No locations to visualize')
        else:
            
            options={'pos':nx.circular_layout(self.nxGraph),'node_color':'darkturquoise','edge_color':'grey','node_size':6000,
                     'width':3,'arrowstyle':'-|>','arrow_size':12}
            if self.vis_path_options is not None:
                options.update(self.vis_path_options)

            if 'fig_size' in options.keys():
                fig_size=[options['fig_size'][0],options['fig_size'][1]]
                del options['fig_size']
            else:
                fig_size=[10,10]

            if 'axis_labels' in options.keys():
                axis_labels=[options['axis_labels'][0],options['axis_labels'][1]]
                del options['axis_labels']
            else:
                axis_labels=['arbitrary axis','arbitrary axis']


            plt.figure('visualize {} paths'.format(self.name),figsize=(fig_size[0],fig_size[1]))
            plt.xlabel(axis_labels[0])
            plt.ylabel(axis_labels[1])
            nx.draw_networkx(self.nxGraph,arrows=True,**options)



    @property
    def status_list(self):
        '''The current location of the device
        
        Returns
        -------
        position : list
        '''
   
        if self.locations is not None:
            loc_list='unknown location'
            for location in self.locations:
                in_position=True
                for i in range(0,len(self.locations[location]),2):
                    axis = self.locations[location][i]
                    value = self.locations[location][i+1]

                    if hasattr(getattr(self,axis),'position'):
                        if isinstance(self.in_band, float):
                            if getattr(self,axis).position < value - self.in_band or \
                                getattr(self,axis).position > value + self.in_band:
                                in_position=False
                        else:
                            if getattr(self,axis).position < self.in_band[location][axis][0] or \
                                getattr(self,axis).position > self.in_band[location][axis][1] :
                                in_position=False

                    elif hasattr(getattr(self,axis),'get'):
                        if isinstance(self.in_band, float):
                            if getattr(self,axis).get() < value - self.in_band or \
                                getattr(self,axis).get() > value + self.in_band:
                                in_position=False
                        else:
                            if getattr(self,axis).get() < self.in_band[location][axis][0] or \
                                getattr(self,axis).get() > self.in_band[location][axis][1] :
                                in_position=False

                    elif hasattr(getattr(self,axis),'status'):
                        if getattr(self,axis).status is not value:
                            in_position=False

                if in_position: 
                    if loc_list == 'unknown location':
                        loc_list = [location]
                    else:
                        loc_list.append(location)
        else:
            loc_list=['no locations']

        return loc_list
   
    @property  
    def status(self):
        '''The current location of the device
        
        Returns
        -------
        position : string
        '''

        if isinstance(self.status_list,list):
            position=''
            for location in self.status_list:
                if len(position)>1:
                    position+=' , '

                position+= location
        else:
            position = self.status_list

        return position
        
