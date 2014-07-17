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
   signals
   schema


Features
--------

- Support for SQLAlchemy models, including:

  - Automatically collects resource fields from models
  - PostgreSQL **JSON & HSTORE** field types
  - Polymorphic model inheritance

- **Embeddable resources** & relationships via :class:`ToOne` and :class:`ToMany` fields
- **Bulk operations** for insert, update, delete
- **Nested resource collections** via :class:`Relationship` properties
- **Resource actions** -- easy to write sub-route functions for resources
- GitHub-style **pagination**
- **Signals** for pre- and post-processing
- Self-documenting **API Schema** for all resources, nested resources and resource methods in
  `JSON Hyper-Schema <http://json-schema.org/latest/json-schema-hypermedia.html>`_ format

Planned Features
^^^^^^^^^^^^^^^^

- Built-in hooks for caching support.
- Support for batch `GET` requests such as ``/resource/1;2;3;4``.
- ``Relationship`` routes with more than one parent
- Built-in query filtering