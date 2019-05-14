from ophyd.telemetry import TelemetryUI


# Start with a test of the generic data entry and extraction process.
def test_telemetry_input_and_output(hw):
    # make an input dictionary
    input_data = {'estimation': {'time': 7.5, 'std_dev': 0.75},
                  'time': {'start': 0, 'stop': 8},
                  'position': {'start': 0, 'stop': 5}}
    # make the output data
    output_data = {'object_name': 'motor1', 'action': 'set'}
    output_data.update(input_data)
    # ensure the telemetry list is empty
    TelemetryUI.telemetry = []
    # run the insert command
    TelemetryUI.record_telemetry('motor1', 'set', input_data)
    # test that the only database entry equals the output data
    assert TelemetryUI.telemetry[0] == output_data
    # fetch the data using the builtin command and test it is as expected
    fetch_data = TelemetryUI.fetch_telemetry('motor1', 'set')[0]
    assert fetch_data == output_data


# RUN SOME TESTS ON AN EpicsMotorEstTime device  `ophyd.sim hw.motor1`.
# test motor set.
def test_telemetry_on_motor_set(hw):
    output_data = {'object_name': 'motor1',
                   'action': 'set',
                   'estimation': {'time': float('nan'),
                                  'std_dev': float('nan')},
                   'time': {'start': float('nan'), 'stop': float('nan')},
                   'position': {'start': 5, 'stop': 3},
                   'velocity': {'setpoint': 1},
                   'settle_time': {'setpoint': 0}}
    hw.motor1.set(5)  # move motor1 to a starting location (5)
    TelemetryUI.telemetry = []  # empty the telemetry database
    hw.motor1.set(3)  # move motor1 to the finishing location (3)
    # test that the keys are the same
    assert TelemetryUI.telemetry[0].keys() == output_data.keys()
    # test that each of the values for all non-time related keys are the same
    for key in ['object_name', 'action', 'position', 'velocity',
                'settle_time']:
        assert TelemetryUI.telemetry[0][key] == output_data[key]

# In the future we will need to add some tests of 'motor.trigger',
# 'motor.stage' and 'motor.unstage' when it is implemented


# RUN SOME TESTS ON AN ADEstTime device `ophyd.sim hw.det1`
# test det trigger.
def test_telemetry_on_det_trigger(hw):
    # In the future, once they are implemented, we will need to modify this to
    # check the `det1.stage` and `det1.unstage` inserts.
    output_data = {'object_name': 'det1',
                   'action': 'trigger',
                   'estimation': {'time': float('nan'),
                                  'std_dev': float('nan')},
                   'time': {'start': float('nan'), 'stop': float('nan')},
                   'trigger_mode': {'setpoint': 1},
                   'num_images': {'setpoint': 1},
                   'settle_time': {'setpoint': 0},
                   'acquire_period': {'setpoint': 1},
                   'acquire_time': {'setpoint': 1}}

    hw.det1.stage()  # stage the detector
    TelemetryUI.telemetry = []  # empty the telemetry database
    hw.det1.trigger()  # trigger the detector
    hw.det1.unstage()
    # test that the keys are the same
    assert TelemetryUI.telemetry[0].keys() == output_data.keys()
    # test that each of the values for all non-time related keys are the same
    for key in ['object_name', 'action', 'trigger_mode', 'num_images',
                'settle_time', 'acquire_period', 'acquire_time']:
        assert TelemetryUI.telemetry[0][key] == output_data[key]
