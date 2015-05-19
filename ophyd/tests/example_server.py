#!/usr/bin/env python

from pcaspy import SimpleServer, Driver
import threading
import subprocess
import random
import shlex
import time
import math


prefix = 'MTEST:'
pvdb = {
    'RAND' : {
        'prec' : 3,
        'scan' : 1,
        'count': 1,
    },
    'COMMAND' : {
        'type' : 'string',
        'asyn' : True,
        'value' : '',
    },
    'OUTPUT'  : {
        'type' : 'string',
        'value' : '',
    },
    'STATUS'  : {
        'type' : 'enum',
        'enums': ['DONE', 'BUSY']
    },
    'ERROR'   : {
        'type' : 'string',
        'value' : '',
    },
}

class myDriver(Driver):
    def __init__(self):
        super(myDriver, self).__init__()
        self.tid = None 

    def read(self, reason):
        if reason == 'RAND':
            value = [random.random() for i in range(10)]
        else:
            value = super(myDriver, self).read(reason)
        return value

    def write(self, reason, value):
        status = True
        # take proper actions
        if reason == 'COMMAND':
            if not self.tid:
                command = value
                self.tid = threading.Thread(target=self.runShell,args=(command,))
                self.tid.start()
            else:
                status = False
        else:
            status = False
        # store the values
        if status:
            self.setParam(reason, value)
        return status

    def runShell(self, command):
        print("DEBUG: Run ", command)
        # set status BUSY
        self.setParam('STATUS', 1)
        self.updatePVs()
        # run shell
        try:
            time.sleep(0.01)
            proc = subprocess.Popen(shlex.split(command), 
                    stdout = subprocess.PIPE, 
                    stderr = subprocess.PIPE)
            proc.wait()
        except OSError:
            self.setParam('ERROR', str(sys.exc_info()[1]))
            self.setParam('OUTPUT', '')
        else:
            self.setParam('ERROR', proc.stderr.read().rstrip())
            self.setParam('OUTPUT', proc.stdout.read().rstrip())
        self.callbackPV('COMMAND')
        # set status DONE
        self.setParam('STATUS', 0)
        self.updatePVs()
        self.tid = None
        print("DEBUG: Finish ", command)

if __name__ == '__main__':
    server = SimpleServer()
    server.createPV(prefix, pvdb)
    driver = myDriver()

    while True:
        # process CA transactions
        server.process(0.1)
