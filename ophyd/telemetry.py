from collections import defaultdict
from statistics import mean, stdev

_telemetry = defaultdict(lambda: \
                defaultdict(lambda: \
                    defaultdict(lambda: \
                        defaultdict(lambda: \
                            defaultdict(list) ) ) ) ) 
#This is a prototype telemetry database, it has the structure:
#   telemetry[object][action][attribute]['setpoint'][value or time] returns a list of values
#   for eg. telemetry['motor_name']['set']['velocity']['setpoint']['value'] returns a list of velocities
#           telemetry['motor_name']['set']['velocity']['setpoint']['time'] returns a list of timestamps


def record_telemetry(obj_name, cmd, data):
    '''This function records a set of value/timestamp tuples into the telemetry database.

    This function is used to record a value/timestamp tuple to the telemetry database (currently a
    dictionary). It takes in the obj_name, a command (or action) and a dictionary where the keywords
    are the attribute names and the values are set_value/measured_value/timestamp tuples.

    PARAMETERS
    ----------
    obj_name, string.
        A string that contains the name of the object/device that the action was performed on.
    cmd, string.
        The name of the action performed on the object/device (matches the actions defined in a 
        plans msg list).
    data, dict.
        A dictionary with keywords corresponding to the attributes that where calculated for the 
        action and values being setpoint/value/timestamp tuples.

    '''
    for attribute in list( data.keys() ):
        _telemetry[obj_name][cmd][attribute][str(data[attribute][0])]\
                                    ['value'].append(data[attribute][1])
        _telemetry[obj_name][cmd][attribute][str(data[attribute][0])]\
                                    ['time'].append(data[attribute][2])


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
        A dictionary with keywords corresponding to the attributes that where stored for the 
        action and values being a dictionary with keywords 'value' and 'time' and values being a 
        matched list of data for both.

    '''
    return _telemetry[obj_name][cmd]



def fetch_statistics(obj_name, cmd, inputs):
    '''This function returns a dictionary with mean/std_dev lists from the telemetry database.

    This function is used to return a dictionary with attribute keywords and  mean/std_dev tuple 
    values from the telemetry database (currently a dictionary). It takes in the obj_name and a 
    command (or action) and returns a dictionary where the keywords are attributes,and the values 
    are mean/std_dev lists. If there are no telemetry values for this object and action it returns
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
        A dictionary with keywords corresponding to the attributes that where stored for the 
        action and values being a mean/ std_dev list.

    '''
    telemetry = fetch_telemetry(obj_name,cmd)
    data = {}    

    for attribute in list(telemetry.keys()):
        data[attribute] = [ mean(telemetry[attribute]['value'][inputs['attribute']]), 
                            stdev(telemetry[attribute]['value'][inputs['attribute']] ) ]

    return data


