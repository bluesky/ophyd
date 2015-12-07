#!/usr/bin/env python
from setuptools import (setup, find_packages)
import versioneer


setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      packages=find_packages())
