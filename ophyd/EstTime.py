from .telemetry import TelemetryUI
from collections import namedtuple
import statistics
import math

#define the statistics error
StatisticsError = statistics.StatisticsError

#define a named tuple classes for use later.
_TimeStats = namedtuple('TimeStats', 'est_time std_dev')
_AttrTuple = namedtuple('AttrTuple', 'name start stop')

#define some functions
record_telemetry = TelemetryUI.record_telemetry
fetch_telemetry = TelemetryUI.fetch_telemetry


class DefaultEstTime:
    '''The base class for the time estimation on all OphydObjs.
    This allows the devices to provide an estimate of how long it takes to perform specific 
    commands on them via the addition of obj.est_time.cmd method attributes. 
    This must also interact with the telemetry class in order to use time statistics if they 
    exist to improve the time estimation.
    '''

    def __init__(self, obj_name):
        '''The initialization method.
        Parameters
        ----------
        obj_name, str
            The object name that this class is being instantiated on.
        '''
        self.obj_name = obj_name


    def set(self, start_pos, target):
        '''Estimates the time (est_time) to perform 'set' on this object.
                
        This method returns an estimated time (est_time) to perform set between start pos and 
        target. If telemetry for this action, and any argument values, exist it uses mean 
        values and works out a standard deviation (std_dev). Otherwise it uses the argument values 
        to determine an est_time and returns float('nan') for both est_time and std_dev.

        PARAMETERS
        ----------
        start_pos: float or string.
            The start position for the set.
        target: float or string.
            The end position for the set.

        RETURNS
        -------
        stats: namedtuple.
            A namedtuple containing the est_time as the first element and the std_dev as the second 
            element.
        '''
        attributes = []
        attributes.append(_AttrTuple('position', start_pos, target)) 

        time_list = self._extract_time_list(fetch_telemetry(self.obj_name,'set'), 
                                                            attributes = attributes)       
        try:
            out_time = _TimeStats(statistics.mean(time_list), statistics.stdev(time_list))
        except StatisticsError:
            try:
                out_time = _TimeStats(statistics.mean(time_list), float('nan'))
            except StatisticsError:
                out_time = _TimeStats(float('nan'), float('nan'))

        return out_time

    def _set_record(status_object = None):
        '''This is a function that records telemetry for the set command.

        PARAMETER
        ---------
        status_object: StatusObject.
            This is a status object that contains information collected about the action to be 
            stored in telemetry.
        '''
        if status_object:
            data={}
            data['estimation'] = {'time':status_object.est_time.est_time, 
                                'std_dev':status_object.est_time.std_dev}
            data['time'] = {'start':status_object.start_ts, 'stop':status_object.finish_ts}
            data['position'] = {'start':status_object.start_pos, 'stop':status_object.finish_pos}

            record_telemetry(status_object.obj_name, 'set', data)

    set.record = _set_record

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
        
        time_list = self._extract_time_list(fetch_telemetry(self.obj_name,'trigger'))        

        try:
            out_time = _TimeStats(statistics.mean(time_list), statistics.stdev(time_list))
        except StatisticsError:
            try:
                out_time = _TimeStats(statistics.mean(time_list), float('nan'))
            except StatisticsError:
                out_time = _TimeStats(float('nan'), float('nan'))

        return out_time



    def _trigger_record(status_object = None):
        '''This is a function that records telemetry for the trigger command.

        PARAMETER
        ---------
        status_object: StatusObject.
            This is a status object that contains information collected about the action to be 
            stored in telemetry.
        '''
        if status_object:
            data={}
            data['estimation'] = {'time':status_object.est_time.est_time, 
                                'std_dev':status_object.est_time.std_dev}
            data['time'] = {'start':status_object.start_ts, 'stop':status_object.finish_ts}

            record_telemetry(status_object.obj_name, 'trigger', data)

    trigger.record = _trigger_record

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

        time_list = self._extract_time_list(fetch_telemetry(self.obj_name,'stage'))        

        try:
            out_time = _TimeStats(statistics.mean(time_list), statistics.stdev(time_list))
        except StatisticsError:
            try:
                out_time = _TimeStats(statistics.mean(time_list), float('nan'))
            except StatisticsError:
                out_time = _TimeStats( float('nan'), float('nan'))

        return out_time

    def _stage_record(status_object = None):
        '''This is a function that records telemetry for the stage command.

        PARAMETER
        ---------
        status_object: StatusObject.
            This is a status object that contains information collected about the action to be 
            stored in telemetry.
        '''

        if status_object:
            data={}
            data['estimation'] = {'time':status_object.est_time.est_time, 
                                'std_dev':status_object.est_time.std_dev}
            data['time'] = {'start':status_object.start_ts, 'stop':status_object.finish_ts}

            record_telemetry(status_object.obj_name, 'stage', data)

    stage.record = _stage_record

    def unstage(self ):
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

        time_list = self._extract_time_list(fetch_telemetry(self.obj_name,'unstage'))        

        try:
            out_time = _TimeStats(statistics.mean(time_list), statistics.stdev(time_list))
        except StatisticsError:
            try:
                out_time = _TimeStats(statistics.mean(time_list), float('nan'))
            except StatisticsError:
                out_time = _TimeStats(float('nan'), float('nan'))

        return out_time

    def _unstage_record(status_object = None):
        '''This is a function that records telemetry for the unstage command.

        PARAMETER
        ---------
        status_object: StatusObject.
            This is a status object that contains information collected about the action to be 
            stored in telemetry.
        '''
        
        if status_object:
            data={}
            data['estimation'] = {'time':status_object.est_time.est_time, 
                                'std_dev':status_object.est_time.std_dev}
            data['time'] = {'start':status_object.start_ts, 'stop':status_object.finish_ts}

            record_telemetry(status_object.obj_name, 'unstage', data)

    unstage.record = _unstage_record


    def _extract_time_list(self, telemetry, attributes = None):
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
        if attributes is not None:
            for attribute in attributes:
                for action in telemetry:
                    if isinstance(attribute.start, float):
                        if not math.isclose(action[attribute.name]['start'],attibute.start,
                                        rel_tol=.01):
                            if attribute['stop'] is None or \
                            not math.isclose(action[attribute.name]['stop'],attibute.stop,
                                        rel_tol=.01):
                                telemetry.remove(action)

                    elif isinstance(attribute.start, str):
                        if action[attribute.name]['start'] is not attribute.start:
                            if attribute.stop is None or \
                             action[attribute.name]['stop'] is not attribute.stop:
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

    def set(self, start_pos, target, velocity, settle_time):
        '''Estimates the time (est_time) to perform 'set' on this object.
                
        This method returns an estimated time (est_time) to perform set between start position and 
        stop position. If telemetry for this action, and any argument values, exist it uses mean 
        values and works out a standard deviation (std_dev). Otherwise it uses the argument values 
        to determine an est_time and returns float('nan') for both est_time and std_dev.

        PARAMETERS
        ----------
        start_pos: float or str.
            The start position for the set.
        target: float or str.
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

        attributes = [_AttrTuple('velocity', velocity, None)]
                     

        velocity_list = self._extract_velocity_list(fetch_telemetry(self.obj_name,'set'), 
                                                attributes = attributes)        

        if velocity_list:
            mean_velocity = statistics.mean(velocity_list)
            try:
                std_dev_velocity = statistics.stdev(velocity_list)
            except StatisticsError:
                std_dev_velocity = float('nan')
        
            if mean_velocity == 0:
                print (f'velocity_list: {velocity_list}')   
                mean_velocity = float('nan')

            est_time = abs(start_pos - target)/mean_velocity + settle_time
            est_time_max = abs(start_pos - target)/(mean_velocity + std_dev_velocity) \
                                + settle_time
            est_time_min = abs(start_pos - target)/(mean_velocity - std_dev_velocity) \
                                + settle_time 

            std_dev_est_time = max( abs( est_time - est_time_max), abs(est_time - est_time_min) )
        
            out_time = _TimeStats(est_time, std_dev_est_time)
        else:

            est_time = abs(start_pos - target)/velocity + settle_time
            out_time = _TimeStats(est_time, float('nan'))

        return out_time

    def _set_record(status_object = None):
        '''This is a function that records telemetry for the set command.

        PARAMETER
        ---------
        status_object: StatusObject.
            This is a status object that contains information collected about the action to be 
            stored in telemetry.
        '''
                
        if status_object:
            data={}
            data['estimation'] = {'time':status_object.est_time.est_time, 
                                    'std_dev':status_object.est_time.std_dev}
            data['time'] = {'start':status_object.start_ts, 'stop':status_object.finish_ts}
            data['position'] = {'start':status_object.start_pos, 'stop':status_object.finish_pos}
            data['velocity'] = {'setpoint':status_object.pos.velocity.position}
            data['settle_time'] = {'setpoint':status_object.pos.settle_time.position}

            record_telemetry(status_object.pos.name, 'set', data)

    set.record = _set_record    
    

    def _extract_velocity_list(self, telemetry, attributes = None):
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

        if attributes is not None:
            for attribute in attributes:
                for action in telemetry:
                    if not math.isclose(action[attribute.name]['setpoint'], attribute.start,
                                        rel_tol=.01):
                        telemetry.remove(action)
        out_list=[]

        for action in telemetry:

            delta_distance = abs(action['position']['start'] - action['position']['stop'])
            delta_time = abs(action['time']['start'] - action['time']['stop'])
            settle_time = action['settle_time']['setpoint']
            out_list.append(delta_distance/(delta_time - settle_time))

        return out_list



class ADEstTime(DefaultEstTime):
    '''This is the EstTime class for the time estimation on AreaDetector Devices.

    This allows the devices to provide an estimate of how long it takes to perform specific 
    commands on them via the addition of obj.est_time and obj.est_time.cmd methods attributes. 
    This must also interact with the 'stats' methods in order to use time statistics if they 
    exist to improve the time estimation.
    '''

    def __init__(self, obj_name):
        '''The initialization method.

        Parameters
        ----------
        obj_name, name of objectobject
            The object name that this class is being instantiated on.
        '''
        self.obj_name = obj_name

  
    def trigger(self, acquire_time, acquire_period, trigger_mode, num_images, settle_time):
        '''Estimates the time (est_time) to perform 'trigger' on this object.

        This method returns an estimated time (est_time) to perform trigge. If telemetry for this 
        action, and any argument values, exist it uses mean values and works out a standard deviation 
        (std_dev). Otherwise it uses the argument values to determine an est_time and returns 
        float('nan') for both est_time and std_dev.

        PARAMETERS
        ----------
        acquire_period: float.
            The acquire period used if trigger_mode is 'fixed'.
        acquire_time: float.
            The acquire time used if trigger_mode is not 'fixed'.
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
            attributes = [_AttrTuple('acquire_period',acquire_time, None)]
        else:
            attributes = [_AttrTuple('acquire_time',acquire_time, None)]

        acquire_time_list = self._extract_acquire_time_list(fetch_telemetry(self.obj_name,'trigger'), 
                                                attributes = attributes)        

        if acquire_time_list:
            mean_acquire_time = statistics.mean(acquire_time_list)
            try:
                std_dev_acquire_time = statistics.stdev(acquire_time_list)
            except StatisticsError:
                std_dev_acquire_time = float('nan')

            est_time = (mean_acquire_time + settle_time) * num_images
            est_time_max = (mean_acquire_time + std_dev_acquire_time + settle_time) * num_images
            est_time_min = (mean_acquire_time - std_dev_acquire_time + settle_time) * num_images

            std_dev_est_time = max( abs( est_time - est_time_max), abs(est_time - est_time_min) )
        
            out_time = _TimeStats(est_time, std_dev_est_time)
        else:
            est_time = (acquire_time + settle_time) * num_images
            out_time = _TimeStats(est_time, float('nan'))

        return out_time

    def _trigger_record(status_object = None):
        '''This is a function that records telemetry for the trigger command.

        PARAMETER
        ---------
        status_object: StatusObject.
            This is a status object that contains information collected about the action to be 
            stored in telemetry.
        '''
        if status_object:
            data={}
            data['estimation'] = {'time':status_object.est_time.est_time, 
                                'std_dev':status_object.est_time.std_dev}
            data['time'] = {'start':status_object.start_ts, 'stop':status_object.finish_ts}
            data['trigger_mode'] = {'setpoint': status_object.device.trigger_mode.position}
            data['num_images'] = {'setpoint': status_object.device.num_images.position}
            data['settle_time'] = {'setpoint' : status_object.device.settle_time.position}
            data['acquire_period'] = {'setpoint': status_object.device.acquire_period.position}
            data['acquire_time'] = {'setpoint' : status_object.device.acquire_time.position} 

            record_telemetry(status_object.device.name, 'trigger', data)

    trigger.record = _trigger_record

    def _extract_acquire_time_list(self, telemetry, attributes = None):
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
                    if not math.isclose(action[attribute.name]['setpoint'], attribute.start,
                                        rel_tol=.01):
                        telemetry.remove(action)

        out_list=[]
        for action in telemetry:
            delta_time = abs(action['time']['start'] - action['time']['stop'])
            num_images = action['num_images']['setpoint']
            settle_time = action['settle_time']['setpoint']

            out_list.append((delta_time/num_images - settle_time))

        return out_list
