
Field types
===========

.. module:: flask_presst.fields

Flask-Presst ships with its own set of fields --- replacing those from Flask-RESTful, and shipping with
additional fields for embedded relationships (:class:`ToOne`, :class:`ToMany` and :class:`ToManyKV`).



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

.. autoclass:: Custom
   :members:

.. autoclass:: Arbitrary
   :members:

.. note::

    ``fields.JSON`` is available as an alias to ``fields.Arbitrary``

.. autoclass:: Object
   :members:

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

Composite field types
---------------------


.. autoclass:: List
   :members:

.. autoclass:: KeyValue
   :members:

