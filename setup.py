#!/usr/bin/env python

from setuptools import setup, find_packages

long_description = open('README.md').read()

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

version = '0.1'

setup(
    name='okysa',
    version=version,
    install_requires=requirements,
    author='x4dr',
    packages=find_packages(),
    include_package_data=True,
    url='https://github.com/x4dr/okysa/',
    license='GPLv3',
    description='discordbot, rewrite of Nossibot from NossiNet',
    long_description=long_description,
    long_description_content_type='text/markdown',
)
