#!/usr/bin/env python
from setuptools import (setup, find_packages)
import versioneer

with open('requirements.txt') as f:
    requirements = f.read().split()


setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      install_requires=requirements,
      packages=find_packages())
