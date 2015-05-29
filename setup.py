#!/usr/bin/env python
from setuptools import setup

setup(name='ophyd',
      version='0.0.6',
      license='BSD',
      packages=['ophyd',
                'ophyd.session',
                'ophyd.controls',
                'ophyd.controls.cas',
                'ophyd.controls.areadetector',
                'ophyd.utils',
                'ophyd.tests'])
