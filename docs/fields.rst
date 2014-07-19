
Field types
===========

.. module:: flask_presst.fields

Flask-Presst ships with its own set of fields --- replacing those from Flask-RESTful with a set more suitable
for JSON-based APIs, and shipping with additional fields for embedded relationships (:class:`ToOne`, :class:`ToMany` and :class:`ToManyKV`).



:class:`Raw` field class
------------------------

.. autoclass:: Raw
   :members:

Embedded field types
--------------------

.. autoclass:: ToOne

.. autoclass:: ToMany

.. autoclass:: ToManyKV


Basic field types
-----------------

.. autoclass:: String
   :members:

.. autoclass:: Integer
   :members:

.. autoclass:: PositiveInteger
   :members:

.. autoclass:: Number
   :members:

.. autoclass:: Boolean
   :members:

.. autoclass:: Date
   :members:

.. autoclass:: DateTime
   :members:

.. autoclass:: Uri
   :members:

.. autoclass:: Email
   :members:

.. autoclass:: Object
   :members:

.. autoclass:: Custom
   :members:

.. autoclass:: Arbitrary
   :members:

Composite field types
---------------------


.. autoclass:: List
   :members:

.. autoclass:: KeyValue
   :members:

