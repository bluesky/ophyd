#!/usr/bin/env python
from setuptools import (setup, find_packages)
import versioneer

with open('requirements.txt') as f:
    requirements = f.read().split()

# Temporary hack until databroker is on PyPI, needed because
# `pip install -r requirements.txt` works with git URLs, but `install_requires`
# does not.
requirements = [r for r in requirements if not r.startswith('git+')]
print("User must install https://github.com/NSLS-II/databroker manually")

setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      install_requires=requirements,
      packages=find_packages())
