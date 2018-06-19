from .telemetry import (fetch_telemetry, fetch_statistics, record_telemetry)
from collections import namedtuple
import math

#define a named tuple classes for use later.
_TimeStats = namedtuple('TimeStats', 'est_time std_dev')
_AttrTuple = namedtuple('AttrTuple', 'name start stop') 


class DefaultEstTime:
    '''The base class for the time estimation on all OphydObjs.
    This allows the devices to provide an estimate of how long it takes to perform specific 
    commands on them via the addition of obj.est_time.cmd method attributes. 
    This must also interact with the telemetry class in order to use time statistics if they 
    exist to improve the time estimation.
    '''

    def __init__(self, obj):
        '''The initialization method.
        Parameters
        ----------
        obj, object
            The object that this class is being instantiated on.
        '''
        self.obj = obj


    def set(self, start_position, stop_position):
        '''Estimates the time (est_time) to perform 'set' on this object.
                
        This method returns an estimated time (est_time) to perform set between start position and 
        stop position. If telemetry for this action, and any argument values, exist it uses mean 
        values and works out a standard deviation (std_dev). Otherwise it uses the argument values 
        to determine an est_time and returns float('nan') for both est_time and std_dev.

        PARAMETERS
        ----------
        start_position: float.
            The start position for the set.
        stop_position: float.
            The end position for the set.

        RETURNS
        -------
        stats: namedtuple.
            A namedtuple containing the est_time as the first element and the std_dev as the second 
            element.
        '''

        attributes = [AttrTuple('position', start_position, stop_position)]   

        time_list = self._extract_time_list(fetch_telemetry(obj.name,'set'), attributes = attributes):        

        if time_list:
            out_time = _TimeStats(mean(time_list), stdev(time_list))
        else:
            out_time = _TimeStats(float('nan'), float('nan'))

        return out_time


    def trigger(self ):
        '''Estimates the time (est_time) to perform 'trigger' on this object.
 
        This method returns an estimated time (est_time) to perform trigger. If telemetry for this 
        action, and any argument values, exist it uses mean values and works out a standard deviation 
        (std_dev). Otherwise it uses the argument values to determine an est_time and returns 
        float('nan') for both est_time and std_dev.
               
        PARAMETERS
        ----------
        None.

        RETURNS
        -------
        stats: namedtuple.
            A namedtuple containing the est_time as the first element and the std_dev as the second 
            element.
        '''

        time_list = self._extract_input_value(fetch_telemetry(obj.name,'trigger')):        

        if time_list:
            out_time = _TimeStats(mean(time_list), stdev(time_list))
        else:
            out_time = _TimeStats(float('nan'), float('nan'))

        return out_time



    def stage(self ):
        '''Estimates the time (est_time) to perform 'stage' on this object.
 
        This method returns an estimated time (est_time) to perform stage. If telemetry for this 
        action, and any argument values, exist it uses mean values and works out a standard deviation 
        (std_dev). Otherwise it uses the argument values to determine an est_time and returns 
        float('nan') for both est_time and std_dev.
               
        PARAMETERS
        ----------
        None.

        RETURNS
        -------
        stats: namedtuple.
            A namedtuple containing the est_time as the first element and the std_dev as the second 
            element.
        '''

        time_list = self._extract_input_value(fetch_telemetry(obj.name,'stage')):        

        if time_list:
            out_time = _TimeStats(mean(time_list), stdev(time_list))
        else:
            out_time = _TimeStats(float('nan'), float('nan'))

        return out_time


    def unstage(self, plan_history = {}, vals = [], record = False):
        '''Estimates the time (est_time) to perform 'unstage' on this object.
 
        This method returns an estimated time (est_time) to perform unstage. If telemetry for this 
        action, and any argument values, exist it uses mean values and works out a standard deviation 
        (std_dev). Otherwise it uses the argument values to determine an est_time and returns 
        float('nan') for both est_time and std_dev.
               
        PARAMETERS
        ----------
        None.

        RETURNS
        -------
        stats: namedtuple.
            A namedtuple containing the est_time as the first element and the std_dev as the second 
            element.
        '''

        time_list = self._extract_input_value(fetch_telemetry(obj.name,'unstage')):        

        if time_list:
            out_time = _TimeStats(mean(time_list), stdev(time_list))
        else:
            out_time = _TimeStats(float('nan'), float('nan'))

        return out_time



    def _extract_time_list(telemetry, attributes = None):
        '''This extracts out all of the values from the 'measured' list that match a start_position
           and a stop_position for an attribute, +/- 1% for floats, in telemetry.
        
        PARAMETERS
        ----------
        telemetry, dict.
            The telemetry dictionary to extract information out of.
        attributes, list of named tuples, optional.
            A list of named tuples relating to a specific attribute, containing (name, start, stop) 
            values. By default this is None and returns the time for every point in the telemetry 
            list. If the attribute does not change during the action then 'stop' should be None.

        RETURNS
        -------
        out_list, list
            A list containing the time for each action. 
        '''
        
        if attribtues is not None:
            for attribute in attributes:
                for action in telemetry:
                    if isinstance(attribute['start'], float):
                        if not math.isclose(action[attribute['name']]['start'],attibute['start'],
                                        rel_tol=.01):
                            if attribute['stop'] is None or
                            not math.isclose(action[attribute['name']]['stop'],attibute['stop'],
                                        rel_tol=.01):
                                telemetry.remove(action)

                    elif isinstance(attribute['start'], str):
                        if action[attribute['name']]['start'] is not attribute['start']:
                            if attribute['stop'] is None or \
                             action[attribute['name']]['stop'] is not attribute['stop']:
                                telemetry.remove(action) 

        out_list=[]
        for action in telemetry:
            out_list.append(action['time']['stop']-action['time']['start'])

        return out_list


class EpicsMotorEstTime(DefaultEstTime):
    '''This is the EstTime class for the time estimation on EpicsMotor Devices.
    This allows the devices to provide an estimate of how long it takes to perform specific 
    commands on them via the addition of obj.est_time and obj.est_time.cmd methods attributes. 
    This must also interact with the 'stats' methods in order to use time statistics if they 
    exist to improve the time estimation.
    '''
     
    def set(self, start_postion, stop_position, velocity, settle_time):
        '''Estimates the time (est_time) to perform 'set' on this object.
                
        This method returns an estimated time (est_time) to perform set between start position and 
        stop position. If telemetry for this action, and any argument values, exist it uses mean 
        values and works out a standard deviation (std_dev). Otherwise it uses the argument values 
        to determine an est_time and returns float('nan') for both est_time and std_dev.

        PARAMETERS
        ----------
        start_position: float.
            The start position ofr the set.
        stop_position: float.
            The end position for the set.
        veloctiy: float.
            The setpoint of the velocity at which the motor moves.
        settle_time: float.
            The amount of time that the device will 'wait' after performing the move.

        RETURNS
        -------
        stats: namedtuple.
            A namedtuple containing the est_time as the first element and the std_dev as the second 
            element.
        '''

        attributes = [AttrTuple('velocity', velocity, None)]
                     

        velocity_list = self._extract_velocity_list(fetch_telemetry(obj.name,'set'), 
                                                attributes = attributes):        

        if time_list:
            mean_velocity = mean(velocity_list)
            std_dev_velocity = stdev(velocity_list)

            est_time = abs(start_position - stop_position)/mean_velocity + settle_time
            est_time_max = abs(start_position - stop_position)/(mean_velocity + std_dev_velocity) \
                                + settle_time
            est_time_min = abs(start_position - stop_position)/(mean_velocity - std_dev_velocity) \
                                + settle_time 

            std_dev_est_time = max( abs( est_time - est_time_max), abs(est_time - est_time_min) )
        
            out_time = _TimeStats(est_time, std_dev_est_time)
        else:
            est_time = abs(start_position - stop_position)/velocity + settle_time
            out_time = _TimeStats(est_time, float('nan'))

        return out_time


    def _extract_velocity_list(telemetry, attributes = None):
        '''This extracts out all of the velocites from the 'measured' list that match a start_position
           and a stop_position for an attribute, +/- 1% for floats, in telemetry.
        
        PARAMETERS
        ----------
        telemetry, dict.
            The telemetry dictionary to extract information out of.
        attributes, list of named tuples, optional.
            A list of named tuples relating to a specific attribute, containing (name, start, stop) 
            values. By default this is None and returns the time for every point in the telemetry 
            list. If the attribute does not change during the action then 'stop' should be None.

        RETURNS
        -------
        out_list, list
            A list containing the velocity for each action. 
        '''
        
        if attribtues is not None:
            for attribute in attributes:
                for action in telemetry:
                    if isinstance(attribute['start'], float):
                        if not math.isclose(action[attribute['name']]['start'],attibute['start'],
                                        rel_tol=.01):
                            if attribute['stop'] is None or
                            not math.isclose(action[attribute['name']]['stop'],attibute['stop'],
                                        rel_tol=.01):
                                telemetry.remove(action)

                    elif isinstance(attribute['start'], str):
                        if action[attribute['name']]['start'] is not attribute['start']:
                            if attribute['stop'] is None or \
                             action[attribute['name']]['stop'] is not attribute['stop']:
                                telemetry.remove(action) 

        out_list=[]
        for action in telemetry:

            delta_distance = abs(action['position']['start'] - action['position']['stop'])
            delta_time = abs(action['time']['start'] - action['time']['stop'])
            settle_time = action['settle_time']['start']

            out_list.append(delta_distance/(delta_time - settle_time))

        return out_list


 


class ADEstTime(DefaultEstTime):
     '''This is the EstTime class for the time estimation on AreaDetector Devices.
    This allows the devices to provide an estimate of how long it takes to perform specific 
    commands on them via the addition of obj.est_time and obj.est_time.cmd methods attributes. 
    This must also interact with the 'stats' methods in order to use time statistics if they 
    exist to improve the time estimation.
    '''

    def __init__(self, obj):
        '''The initialization method.
        Parameters
        ----------
        obj, object
            The object that this class is being instantiated on.
        '''
        self.obj = obj

  
    def trigger(self, acquire_time, trigger_mode, num_images, settle_time):
       '''Estimates the time (est_time) to perform 'trigger' on this object.
                
        This method returns an estimated time (est_time) to perform trigge. If telemetry for this 
        action, and any argument values, exist it uses mean values and works out a standard deviation 
        (std_dev). Otherwise it uses the argument values to determine an est_time and returns 
        float('nan') for both est_time and std_dev.

        PARAMETERS
        ----------
        acquire_period: float.
            The acquire_time (or acquire period if trigger_mode is 'fixed_mode'.
        trigger_mode: string.
            The trigger_mode.
        num_images: int.
            The number of images per step.
        settle_time: float.
            The amount of time that the device will 'wait' after performing the move.

        RETURNS
        -------
        stats: namedtuple.
            A namedtuple containing the est_time as the first element and the std_dev as the second 
            element.
        '''
        
        if trigger_mode is 'fixed_mode':
            attributes = [AttrTuple('acquire_period',acquire_time, None)]
        else:
            attributes = [AttrTuple('acquire_time',acquire_time, None)]

        acquire_time_list = self._extract_acquire_time_list(fetch_telemetry(obj.name,'trigger'), 
                                                attributes = attributes):        

        if time_list:
            mean_acquire_time = mean(acquire_time_list)
            std_dev_acquire_time = stdev(acquire_time_list)

            est_time = (mean_acquire_time + settle_time) * num_images
            est_time_max = (mean_acquire_time + std_dev_acquire_time + settle_time) * num_images
            est_time_min = (mean_acquire_time - std_dev_acquire_time + settle_time) * num_images

            std_dev_est_time = max( abs( est_time - est_time_max), abs(est_time - est_time_min) )
        
            out_time = _TimeStats(est_time, std_dev_est_time)
        else:
            est_time = (acquire_time + settle_time) * num_images
            out_time = _TimeStats(est_time, float('nan'))

        return out_time


    def _extract_acquire_time_list(telemetry, attributes = None):
        '''This extracts out all of the acquire_periods/ aqcuire_times from the 'measured' list that 
           match a start_position and a stop_position for an attribute, +/- 1% for floats, in telemetry.
        
        PARAMETERS
        ----------
        telemetry: dict.
            The telemetry dictionary to extract information out of.
        attributes: list of named tuples, optional.
            A list of named tuples relating to a specific attribute, containing (name, start, stop) 
            values. By default this is None and returns the time for every point in the telemetry 
            list. If the attribute does not change during the action then 'stop' should be None.

        RETURNS
        -------
        out_list, list
            A list containing the velocity for each action. 
        '''
        
        if attributes is not None:
            for attribute in attributes:
                for action in telemetry:
                    if isinstance(attribute['start'], float):
                        if not math.isclose(action[attribute['name']]['start'],attibute['start'],
                                        rel_tol=.01):
                            if attribute['stop'] is None or
                            not math.isclose(action[attribute['name']]['stop'],attibute['stop'],
                                        rel_tol=.01):
                                telemetry.remove(action)

                    elif isinstance(attribute['start'], str):
                        if action[attribute['name']]['start'] is not attribute['start']:
                            if attribute['stop'] is None or \
                             action[attribute['name']]['stop'] is not attribute['stop']:
                                telemetry.remove(action) 

        out_list=[]
        for action in telemetry:
            delta_time = abs(action['time']['start'] - action['time']['stop'])
            num_images = action['num_images']['start']
            settle_time = action['settle_time']['start']

            out_list.append((delta_time/num_images - settle_time))

        return out_list



