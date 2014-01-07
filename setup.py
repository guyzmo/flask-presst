#!/usr/bin/env python
# coding=utf-8
from setuptools import setup, find_packages

setup(
    author=u'Lars Schöning',
    author_email='lays@biosustain.dtu.dk',
    name='Flask-Presst',
    version='',
    packages=['tests', 'examples', 'flask_presst', 'flask_presst.utils'],
    url='https://github.com/biosustain/flask-presst',
    license='MIT',
    test_suite='nose.collector',
    description='REST API framework for Flask and SQLAlchemy',
    setup_requires=[
        'nose>=1.1.2',
    ],
    install_requires=[
        'Flask>=0.8',
        'Flask-RESTful>=0.2.10',
        'Flask-SQLAlchemy>=1.0',
        'iso8601>=0.1.8',
        'six>=1.3.0',
    ],
)