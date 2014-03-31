# Flask-Presst

[![Build Status](https://travis-ci.org/biosustain/flask-presst.png)](https://travis-ci.org/biosustain/flask-presst)
[![Coverage Status](https://coveralls.io/repos/biosustain/flask-presst/badge.png?branch=master)](https://coveralls.io/r/biosustain/flask-presst?branch=master)
[![PyPI version](https://badge.fury.io/py/Flask-Presst.png)](http://badge.fury.io/py/Flask-Presst)
[![Requirements Status](https://requires.io/github/biosustain/flask-presst/requirements.png?branch=master)](https://requires.io/github/biosustain/flask-presst/requirements/?branch=master)

**Flask-Presst** is a Flask extension for REST APIs using the SQLAlchemy ORM and PostgreSQL. The extension has
supports nesting and embedding of resources and powerful resource methods.

## User's Guide

The user guide and documentation is published [here](http://flask-presst.readthedocs.org/en/latest/).

## Features

- Support for SQLAlchemy models, including:
  - PostgreSQL **JSON & HSTORE** field types
  - **Model inheritance**
- **Embeddable resources** & relationships
- **Nested resources**
- **Resource methods**
- GitHub-style **pagination**
- **Signals** for pre- and post-processing
- Self-documenting **API Schema** for all resources, nested resources and resource methods