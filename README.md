# Flask-Presst

[![Build Status](https://travis-ci.org/biosustain/flask-presst.png)](https://travis-ci.org/biosustain/flask-presst)
[![Coverage Status](https://coveralls.io/repos/biosustain/flask-presst/badge.png?branch=master)](https://coveralls.io/r/biosustain/flask-presst?branch=master)
[![PyPI version](https://badge.fury.io/py/Flask-Presst.png)](http://badge.fury.io/py/Flask-Presst)
[![Requirements Status](https://requires.io/github/biosustain/flask-presst/requirements.png?branch=master)](https://requires.io/github/biosustain/flask-presst/requirements/?branch=master)

**Flask-Presst** is a Flask extension for REST APIs using the SQLAlchemy ORM. The extension
supports nesting and embedding of resources and powerful resource methods.

Flask-Presst also comes with an optional easy to use permissions system.

## User's Guide

The user guide and documentation is published [here](http://flask-presst.readthedocs.org/en/latest/).

## Features

- Support for SQLAlchemy models
- Embeddable resources & item references
- Bulk operations for insert, update, delete
- Relationship routes between resources
- Resource actions — easy-to-write sub-route functions for resources
- GitHub-style pagination
- Signals for pre- and post-processing
- Object- & Role-based permissions system *(use optional)*
- Self-documenting JSON Hyper-Schema for all resource routes