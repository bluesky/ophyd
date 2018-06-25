
class TelemetryClass:


    def __init__(self ):

        self.telemetry = []
        #This is a prototype telemetry database, it has the structure:
        #   telemetry[ {timestamp: '', object_name: '', action: '', time: {'start': '', 'stop': ''}, 
        #               attribute_1_name{'start':'', 'stop':''}......... 
        #               attribute_n_name{'start': '', 'stop': ''} }, ............]



    def record_telemetry(self,obj_name, cmd, data):
        '''This function records a set of value/timestamp tuples into the telemetry database.

        This function is used to record a value/timestamp tuple to the telemetry database (currently a
        dictionary). It takes in the obj_name, a command (or action) and a dictionary where the optional
        keywords are the attribute names and the values are set_value/measured_value/timestamp tuples. In 
        addition it always has the unique keyword 'time' with a value being a 
        estimated_value/measured_value/timestamp tuple and may contain an optional keyword 'position' with
        a value being a start_position/stop_position/timestamp tuple (mainly for motor-like 'set' actions).

        PARAMETERS
        ----------
        obj_name, string.
            A string that contains the name of the object/device that the action was performed on.
        cmd, string.
            The name of the action performed on the object/device (matches the actions defined in a 
            plans msg list).
        data, dict.
            A dictionary with a keyword 'time' and a value being an start_time/stop_time 
            tuple. It may also contain optional keywords corresponding to the attributes 
            that where set for the action and values being start value/stop value tuples.
        '''
        event_dict = {}

        event_dict['object_name'] = obj_name
        event_dict['action'] = cmd

        for attribute in data:
            temp_dict={}
            for key in data[attribute]:
                temp_dict[key] = data[attribute][key]
            event_dict[attribute] = temp_dict

        self.telemetry.append(event_dict)


    def fetch_telemetry(self, obj_name, cmd ):
        '''This function returns a dictionary with value and timestamp lists from the telemetry database.

        This function is used to return a dictionary with value and timestamp lists from the telemetry 
        database (currently a dictionary). It takes in the obj_name and a command (or action) and returns
        a dictionary where the keywords are attributes, the values are another dictionary with keywords
        for 'value' and 'time' and values being matched lists of data. If there are no telemetry values 
        for this object and action it returns an empty dictionary.

        PARAMETERS
        ----------
        obj_name, string.
            A string that contains the name of the object/device that the action was performed on.
        cmd, string.
            The name of the action performed on the object/device (matches the actions defined in a 
            plans msg list).

        RETURNS
        -------
        data, dict.
            A dictionary with the keyword 'time' and a value being a dictionary with keywords 'estimated', 
            'measured' and 'timestamp' and values being a matched list of each. Data may also include 
            keywords corresponding to the attributes, that where stored for the action, and values being 
            a dictionary with keywords 'input', 'measured' and 'timestamp' and values being a matched list 
            of data for each. A final optional keyword for data is 'position' whose value is a dictionary 
            with the keywords 'start_position','stop_position' and 'timestamp' with a matched list 
            of values for each.

        '''
        out_list = []
        for item in self.telemetry:
            if item['object_name'] == obj_name and item['action'] == cmd:
                out_list.append(item)

        return out_list

TelemetryUI = TelemetryClass()

