.. Flask-Presst documentation master file, created by
   sphinx-quickstart on Fri Mar 28 16:41:50 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Flask-Presst
============

**Flask-Presst** is a Flask extension for building RESTful APIs that map to the SQLAlchemy ORM. The extension
supports nesting and embedding of resources and powerful resource methods.

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
   resource_methods
   resources
   signals
   schema


Features
--------

- Support for SQLAlchemy models, including:

  - PostgreSQL **JSON & HSTORE** field types
  - **Model inheritance**

- **Embeddable resources** & relationships via :class:`ToOne` and :class:`ToMany` fields
- **Nested resources** via :class:`Relationship` properties
- **Resource methods**
- GitHub-style **pagination**
- **Signals** for pre- and post-processing
- Self-documenting **API Schema** for all resources, nested resources and resource methods in
  `JSON Hyper-Schema <http://json-schema.org/latest/json-schema-hypermedia.html>`_ format

Planned Features
^^^^^^^^^^^^^^^^

- Built-in hooks for caching support.
- Support for batch requests such as ``/resource/1;2;3;4`` with atomicity through nested transactions.
- Support for *document-like* batch insertion of resources with embedded items.
- True child resources for non-polymorphic models with foreign-key primary keys.
- Support multiple resource methods of the same name using method prefixes, e.g. ``GET_addresses``,
  ``POST_addresses``; alternatively make child resources simple enough to support this scenario.
