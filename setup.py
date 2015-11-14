#!/usr/bin/env python
from setuptools import setup
import versioneer


setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      packages=['ophyd',
                'ophyd.session',
                'ophyd.controls',
                'ophyd.controls.areadetector',
                'ophyd.utils',
                'ophyd.tests'])
