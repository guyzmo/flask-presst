
================================
Relationships & Resource nesting
================================

.. module:: flask_presst

Relationships create routes from one :class:`PresstResource` to another. When used with :class:`ModelResource`,
the attribute name of the resource must be that of a :func:`sqlalchemy.orm.relationship`.

Usage example:

.. code-block:: python

    class AuthorResource(ModelResource):
        books = Relationship(BookResource)  # or Relationship(Book) or Relationship('book')

        class Meta:
            model = Author



.. autoclass:: Relationship
   :members: get, post, delete
