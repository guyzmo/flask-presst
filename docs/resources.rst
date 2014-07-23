
Resource classes
================

.. module:: flask_presst

There are three Resource classes that ship with Flask-Presst:

- :class:`Resource`: a base class for item collections.
- :class:`ModelResource`: primary class for SQLAlchemy models.

All of these resource classes are designed to be extended, for instance to implement authentication or resource
permissions.

The Base-class
--------------


.. autoclass:: Resource
   :members:


:class:`ModelResource` for SQLAlchemy models
--------------------------------------------

.. autoclass:: ModelResource
