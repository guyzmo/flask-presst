.. Flask-Presst documentation master file, created by
   sphinx-quickstart on Fri Mar 28 16:41:50 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Flask-Presst
============

**Flask-Presst** is a Flask extension for building ReSTful APIs that map to the SQLAlchemy ORM. Flask-Presst has
embedding and bulk update capabilities and support for resource action sub-routes.

Flask-Presst is built on top of
`Flask-RESTful <https://github.com/twilio/flask-restful>`_ and can be used together with other Flask-RESTful resources.
Flask-Presst also depends on `Flask <http://flask.pocoo.org/>`_,
`Flask-SQLAlchemy <http://pythonhosted.org/Flask-SQLAlchemy/>`_ and `Blinker <http://pythonhosted.org/blinker/>`_.

Flask-Presst also ships with a simple yet flexible Object- & Role-based permissions system built on `Flask-Principal <https://pythonhosted.org/Flask-Principal/>`_.

User's guide
------------

.. toctree::
   :maxdepth: 2

   installation
   quickstart
   fields
   relationship
   resource_actions
   resources
   permissions
   schema
   signals

Features
--------

- Support for SQLAlchemy models, including:

  - Automatic resource schema generation from models
  - PostgreSQL JSON & HSTORE field type support
  - PostgreSQL polymorphic model inheritance

- Embeddable resources & item references via :class:`ToOne` and :class:`ToMany` fields
- Bulk insert & document insert
- Establish relationship routes via :class:`Relationship` properties
- Resource actions --- easy-to-write sub-route functions for resources
- GitHub-style pagination
- Signals for pre- and post-processing
- Object- & Role-based permissions system *(use optional)*
- Self-documenting API Schema for all resources, embedded resources and resource actions in
  `JSON Hyper-Schema <http://json-schema.org/latest/json-schema-hypermedia.html>`_ format

Planned Features
^^^^^^^^^^^^^^^^

- Built-in hooks for caching support.
- Support for batch `GET` requests such as ``/resource/1;2;3;4``.
- ``Relationship`` routes with more than one parent
- Built-in filtering via query string parameters