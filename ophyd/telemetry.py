from collections import defaultdict, namedtuple
from statistics import mean, stdev

_telemetry = defaultdict(lambda: \
                defaultdict(lambda: \
                    defaultdict(lambda: \
                        defaultdict(list) ) ) ) 

#This is a prototype telemetry database, it has the structure:
#   telemetry[object][action][attribute][value or timestampe] returns a list of values
#   for eg. telemetry['motor_name']['set']['velocity']['estimated'] 
#                                        - returns a list of estimated velocities prior to the moves
#           telemetry['motor_name']['set']['velocity']['measured'] 
#                                        - returns a list of measured velocities after the moves
#           telemetry['motor_name']['set']['velocity']['timestamp'] 
#                                        - returns a list of timestamps


_Stats_tuple = namedtuple('Stats_tuple', 'mean std_dev')

def record_telemetry(obj_name, cmd, data):
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
        A dictionary with a keyword 'time' and a value being an estimated_time/measured_time/ 
        timestamp tuple. It may also contain optional keywords corresponding to the attributes 
        that where calculated for the action and values being setpoint/value/timestamp tuples.
        A final optional keyword 'position' with a value being a start_position/stop_position/
        timestamp tuple may also be included, mainly for motor-like set actions.
    '''
    for attribute in data:
        if attribute == 'time':
            _telemetry[obj_name][cmd][attribute]['estimated'].append(data[attribute][0])
            _telemetry[obj_name][cmd][attribute]['measured'].append(data[attribute][1])
            _telemetry[obj_name][cmd][attribute]['timestamp'].append(data[attribute][2])

        elif attribute == 'position':
            _telemetry[obj_name][cmd][attribute]['start_position'].append(data[attribute][0])
            _telemetry[obj_name][cmd][attribute]['stop_position'].append(data[attribute][1])
            _telemetry[obj_name][cmd][attribute]['timestamp'].append(data[attribute][2])

        else:
            _telemetry[obj_name][cmd][attribute]['input'].append(data[attribute][0])
            _telemetry[obj_name][cmd][attribute]['measured'].append(data[attribute][1])
            _telemetry[obj_name][cmd][attribute]['timestamp'].append(data[attribute][2])



def fetch_telemetry(obj_name, cmd ):
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
    return _telemetry[obj_name][cmd]



def fetch_statistics(obj_name, cmd, inputs):
    '''This function returns a dictionary with mean/std_dev of the lists from the telemetry database.

    This function is used to return a dictionary with attribute keywords and  mean/std_dev list 
    values from the telemetry database (currently a dictionary). It takes in the obj_name and a 
    command (or action) and returns a dictionary where the keyword is 'time' and the value is a 
    mean/std_dev tuple for the time to perform this task. Optional keywords for each attribute
    that is used in the estimated time calculation are also included, with the values being 
    mean/std_dev lists. If there are no telemetry values for this object and action it returns
    an empty dictionary.

    PARAMETERS
    ----------
    obj_name, string.
        A string that contains the name of the object/device that the action was performed on.
    cmd, string.
        The name of the action performed on the object/device (matches the actions defined in a 
        plans msg list).
    inputs, dictionary.
        A dictionary that contains the 'setpoints' for of the attributes, with the attribute names
        as keywords and the setpoints as values.

    RETURNS
    -------
    data, dict.
    A dictionary where the keyword is 'time' and the value is a mean/std_dev namedtuple for the time 
    to perform this task. Optional keywords for each attribute that is used in the estimated time 
    calculation are also included, with the values being mean/std_dev namedtuples. If there are no 
    telemetry values for this object and action it returns an empty dictionary.

    '''
    telemetry = fetch_telemetry(obj_name,cmd)
    data = {}
    
    def extract_input_value(telemetry, attribute, input_value):
        '''This extracts out all of the values from the 'measured' list that match an input_value in
           the 'input' list, +/- 1% for floats, of telemetry.
        
        PARAMETERS
        ----------
        telemetry, dict.
            The telemetry dictionary to extract information out of.
        attribute, str.
            The name of the attribute to extract out the information for.
        input_value, float.
            The setpoint for which to extract out the information regarding.
        RETURNS
        -------
        out_list, list
            A list containing the values relating to the input_value.

        '''
        out_list = []
        for i, val in enumerate(telemetry[attribute]['input']):
            if isinstance(input_value, float): 
                if val > input_value*0.99 and val < input_value*1.01:
                    out_list.append(telemetry[attribute]['measured'][i])
            else:
                if val == input_value:
                    out_list.append(telemetry[attribute]['measured'][i])

        return out_list


    try:
        mean_val = mean(telemetry['time']['measured'])
        try:
            std_dev = stdev(telemetry['time']['measured'] ) 
        except:
            std_dev = float('nan')
                    
        stats = _Stats_tuple(mean_val, std_dev)
        data['time'] = stats
    except:
        pass
    

    for attr in (attr for attr in telemetry if attr not in ['time','position']):
        try:
            mean_val = mean(extract_input_value(telemetry, attr, inputs[attr]))
            try:
                std_dev = stdev(extract_input_value(telemetry, attr, inputs[attr]))
            except:
                std_dev = float('nan')
                    
            stats = _Stats_tuple(mean_val, std_dev)
            data[attr] = stats

        except: 
            pass

    return data


