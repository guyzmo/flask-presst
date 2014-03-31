
Field types
===========

.. module:: flask.ext.presst

Flask-Pressts inherits most of its fields from Flask-RESTful. Some additional fields exist to represent common column
types (namely :class:`fields.Date`) and for relationships (:class:`fields.ToOne` and :class:`fields.ToMany`).

.. module:: flask.ext.presst.fields

Relationship field types
------------------------

.. autoclass:: ToOne
   :members: python_type, resource_class

.. autoclass:: ToMany
   :members: python_type, resource_class

Column type field types
-----------------------

.. autoclass:: KeyValue
   :members:

.. autoclass:: JSON
   :members:

.. autoclass:: Date
   :members:


Flask-Presst fields and parsing
-------------------------------

The custom fields that ship with Flask-Presst all have a property ``python_type``, which must be a callable that takes
one argument to convert into the field type. The callable must raise an exception, preferably a :class:`TypeError`,
if the argument cannot be converted. Field types that follow this standard will be parsed properly by Flask-Presst.