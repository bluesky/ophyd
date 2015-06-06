from __future__ import print_function

import time
import sys

from ophyd.runengine.run import Run


def startrun(msg='client_startrun', **kwargs):
    print(msg)
    time.sleep(2)

def endrun(msg='client_endrun', **kwargs):
    print(msg)

def pauserun(msg='client_pauserun', **kwargs):
    print(msg)
    time.sleep(2)

def resumerun(msg='client_resumerun', **kwargs):
    print(msg)

def scanning(msg='client_scanning', **kwargs):
    print(msg)
    print('moving')
    print('waiting')
    print('acquiring')
    print('waiting')
    print('reading')
    print('saving\n\n')
    time.sleep(1)

# Test things that DON'T work yet
run = Run()
events = ['periodic', 'signal', 'scaler']
def foo(): pass
for ev in events:
    try:
        run.subscribe(foo, event_type=ev)
    except NotImplementedError as ex:
        print(ex)

# a Run with no callbacks should generate start/end_run
# and nothing else
print('\n\ntry a basic run...\n\n')
run = Run()
run.start()

print('\n\ntry some subscriptions\n\n')
run = Run()

run.subscribe(startrun, event_type='start_run')
run.subscribe(endrun, event_type='end_run')
run.subscribe(pauserun, event_type='pause_run')
run.subscribe(resumerun, event_type='resume_run')
run.subscribe(scanning, event_type='trajectory_scan')

run.start()
