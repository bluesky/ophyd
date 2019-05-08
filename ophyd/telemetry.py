import pymongo
import yaml
import os
import sys


class TelemetryClass:

    def __init__(self):

        self.telemetry = []
        # This is a prototype telemetry database, it has the structure:
        #   telemetry[ {timestamp: '', object_name: '', action: '',
        #               time: {'start': '', 'stop': ''},
        #       attribute_1_name{'start':'', 'stop':''}.........
        #       attribute_n_name{'start': '', 'stop': ''} }, ............]

        self.use_database = False
        # allows for hot swapping between the dictionary (self.telemetry)
        # and a mongo database.

        self._client = None
        self.telemetry_db = None

    if os.name == 'nt':
        _user_conf = os.path.join(os.environ['APPDATA'], 'telemetry')
        CONFIG_SEARCH_PATH = (_user_conf,)
    else:
        _user_conf = os.path.join(os.path.expanduser('~'), '.config',
                                  'telemetry')
        _local_etc = os.path.join(os.path.dirname(os.path.dirname(
                                  sys.executable)), 'etc', 'telemetry')
        _system_etc = os.path.join('/', 'etc', 'telemetry')
        CONFIG_SEARCH_PATH = (_user_conf, _local_etc, _system_etc)

    def record_telemetry(self, obj_name, cmd, data):
        '''This function records a set of value/timestamp tuples into the
        telemetry database.

        This function is used to record a value/timestamp tuple to the
        telemetry database (currently a dictionary). It takes in the obj_name,
        a command (or action) and a dictionary where the optional keywords are
        the attribute names and the values are set_value/measured_value/
        timestamp tuples. In addition it always has the unique keyword 'time'
        with a value being a estimated_value/measured_value/timestamp tuple and
        may contain an optional keyword 'position' with a value being a
        start_position/stop_position/timestamp tuple (mainly for motor-like
        'set' actions).

        PARAMETERS
        ----------
        obj_name : string.
            A string that contains the name of the object/device that the
            action was performed on.
        cmd : string.
            The name of the action performed on the object/device (matches the
            actions defined in a plans msg list).
        data : dict.
            A dictionary with a keyword 'time' and a value being an start_time
            /stop_time tuple. It may also contain optional keywords
            corresponding to the attributes that where set for the action and
            values being start value/stop value tuples.
        '''
        event_dict = {}

        event_dict['object_name'] = obj_name
        event_dict['action'] = cmd

        for attribute in data:
            temp_dict = {}
            for key in data[attribute]:
                temp_dict[key] = data[attribute][key]
            event_dict[attribute] = temp_dict

        if self.use_database:
            self.telemetry_db.posts.insert_one(event_dict)
        else:
            self.telemetry.append(event_dict)

    def fetch_telemetry(self, obj_name, cmd):
        '''This function returns a dictionary with value and timestamp lists
           from the telemetry database.

        This function is used to return a dictionary with value and timestamp
        lists from the telemetry database (currently a dictionary). It takes
        in the obj_name and a command (or action) and returns a dictionary
        where the keywords are attributes, the values are another dictionary
        with keywords for 'value' and 'time' and values being matched lists of
        data. If there are no telemetry values for this object and action it
        returns an empty dictionary.

        PARAMETERS
        ----------
        obj_name : string.
            A string that contains the name of the object/device that the
            action was performed on.
        cmd : string.
            The name of the action performed on the object/device (matches the
            actions defined in a plans msg list).

        RETURNS
        -------
        data : dict.
            A dictionary with the keyword 'time' and a value being a dictionary
            with keywords 'estimated', 'measured' and 'timestamp' and values
            being a matched list of each. Data may also include keywords
            corresponding to the attributes, that where stored for the action,
            and values being a dictionary with keywords 'input', 'measured' and
            'timestamp' and values being a matched list of data for each. A
            final optional keyword for data is 'position' whose value is a
            dictionary with the keywords 'start_position','stop_position' and
            'timestamp' with a matched list of values for each.
        '''
        if self.use_database:
            out_list = list(self.telemetry_db.posts.find(
                            {'object_name': obj_name, 'action': cmd}))
        else:
            out_list = []
            for item in self.telemetry:
                if item['object_name'] == obj_name and item['action'] == cmd:
                    out_list.append(item)

        return out_list

    def lookup_config(self, name):
        """
        Search for a databroker configuration file with a given name.
        For exmaple, the name 'example' will cause the function to search for:
        * ``~/.config/databroker/example.yml``
        * ``{python}/../etc/databroker/example.yml``
        * ``/etc/databroker/example.yml``
        where ``{python}`` is the location of the current Python binary, as
        reported by ``sys.executable``. It will use the first match it finds.
        The configuration file should have the structure:
        >>> config = {
        ...     'description': 'lightweight personal database',
        ...     'telemetry': {
        ...         'config': {
        ...             'host' : 'some_host',
        ...             'port' : 'some_port',
        ...             'database' : 'some database name'}
        ...                   },
        ...                  }
        ...          }

        Parameters
        ----------
        name : string

        Returns
        -------
        config : dict
        """

        if not name.endswith('.yml'):
            name += '.yml'
        tried = []
        for path in self.CONFIG_SEARCH_PATH:
            filename = os.path.join(path, name)
            tried.append(filename)
            if os.path.isfile(filename):
                with open(filename) as f:
                    return yaml.load(f)
        else:
            raise FileNotFoundError("No config file named {!r} could be found"
                                    "in the following locations:\n{}"
                                    "".format(name, '\n'.join(tried)))

    def configure_db(self, name=None):
        """
        Create a new Broker instance using a dictionary of configuration.
        Parameters
        ----------
        config : dict
        name : str, optional
            The name of the generated Broker
        Returns
        -------
        db : Broker
        Examples
        --------
        Create a Broker backed by sqlite databases. (This is configuration is
        not recommended for large or important deployments. See the
        configuration documentation for more.)
        """

        # Import component classes.
        if self.telemetry_db is None:
            config = self.lookup_config('name')

            if self._client is None:
                self._client = pymongo.MongoClient(self.config['host'],
                                                   self.config.get('port',
                                                                   None))

            self.telemetry_db = self._client(config['database'])


TelemetryUI = TelemetryClass()
