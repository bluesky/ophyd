import threading
import time
from ophyd import Kind
from ophyd.ophydobj import OphydObject
import serial


class SerialSignal(OphydObject):
    def __init__(
        self,
        *,
        name,
        parent=None,
        kind=Kind.hinted,
        labels=None,
        attr_name="",
        **kwargs
    ):

        super().__init__(
            name=name, parent=parent, kind=kind, labels=labels, attr_name=attr_name
        )

        self.ser = serial.Serial(**kwargs)

    def _setup_uhl(self):
        self.ser.close()
        self.ser.open()


class SerialDevice(OphydObject):
    def __init__(self, ser, *, name):
        pass


def open_uhl():
    # configure the serial connections (the parameters differs on the device you are connecting to)
    ser = serial.Serial(
        port="COM1",
        baudrate=9600,
        rtscts=True,
        timeout=30,
        parity="N",
        stopbits=2,
        bytesize=8,
        # write_timeout=10
    )
    ser.close()
    ser.open()
    # initializing
    ser.write(b"Reset\r")
    time.sleep(0.2)
    ser.write(b"!ctr 0 0 0\r")
    time.sleep(0.2)
    ser.write(b"!dim 1 1 1\r")
    time.sleep(0.2)
    ser.write(b"!axis 1 1 1\r")
    time.sleep(0.2)
    ser.write(b"!pitch 4.0 4.0 1.0\r")
    time.sleep(0.2)
    ser.write(b"!encperiod 0.004 0.004 0.004\r")
    time.sleep(0.2)
    ser.write(b"!accel 0.25 0.25 0.25\r")
    time.sleep(0.2)
    ser.write(b"!vel 10 10 15\r")
    time.sleep(0.2)
    ser.write(b"!encpos 1\r")
    time.sleep(0.2)
    ser.write(b"!twi 0.006 0.006 0.006\r")
    time.sleep(0.2)
    ser.write(b"!ctr 2 2 2\r")
    time.sleep(0.2)
    return ser


def move_to_xy(ser, x, y):
    # IMPORTANT movement here is ABSOLUTE
    move_command = ("!moa " + str(x) + " " + str(y) + " 0\r").encode("UTF-8")
    ser.write(move_command)
    time.sleep(3)


def close_uhl(ser):
    ser.close()
    print("UHL port closed!")


x = 5000
y = 5000
ser = open_uhl()
move_to_xy(ser, x, y)
close_uhl(ser)
