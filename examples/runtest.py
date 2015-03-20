from __future__ import print_function

from ophyd.runengine.run import *


def foo(msg='foo'):
    print(msg)

def bar(msg='bar'):
    print(msg)

def baz(msg='baz'):
    print(msg)

run_num = 11

run = Run(run_num)

run.trigger(foo, every=Run.BEGIN_RUN, msg='\n\n\tFoo msg...\n\n')
run.trigger(bar, every=Run.END_RUN, msg='\n\n\tBar msg...\n\n')
run.trigger(baz, every=Run.SCAN_EV, msg='\n\n\tBaz msg...\n\n')
run.start()
