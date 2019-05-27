#!/usr/bin/env python
import os
from setuptools import (setup, find_packages)
import versioneer

here = os.path.abspath(os.path.dirname(__file__))

# Get the requirements from requirements.txt
with open(os.path.join(here, 'requirements.txt'), 'rt') as f:
    requirements = f.read().split()

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), 'rt', encoding='utf-8') as f:
    long_description = f.read()

setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      long_description=long_description,
      long_description_content_type='text/markdown',
      license='BSD',
      python_requires='>=3.6',
      install_requires=requirements,
      packages=find_packages(),
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
      ])
