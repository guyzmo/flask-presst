#!/usr/bin/env python
# coding=utf-8
from __future__ import unicode_literals
from setuptools import setup, find_packages

setup(
    author='Lars Schoening',
    author_email='lays@biosustain.dtu.dk',
    name='Flask-Presst',
    version='0.3.2',
    packages=find_packages(exclude=['*tests*']),
    url='https://flask-presst.readthedocs.org/en/latest/',
    license='MIT',
    test_suite='nose.collector',
    description='REST API framework for Flask and SQLAlchemy',
    tests_require=[
        'Flask-Testing>=0.4.1',
        'Flask-Principal',
        'nose>=1.1.2',
        'mock',
    ],
    install_requires=[
        'Flask>=0.10',
        'Flask-RESTful>=0.2.10',
        'Flask-SQLAlchemy>=1.0',
        'jsonschema>=2.3.0',
        'iso8601>=0.1.8',
        'blinker>=1.3',
        'six>=1.3.0'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    zip_safe=False,
    extras_require={
        'docs': ['sphinx', 'Flask-Principal'],
        'principal': [
            'Flask-Principal',
        ]
    }
)