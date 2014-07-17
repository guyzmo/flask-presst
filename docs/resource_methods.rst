
Resource methods
================

Resource methods allow you to define additional routes to a resource without having to define an entirely new
resource. The :func:`resource_method` decorator is one out of two ways to nest additional routes within a
:class:`PresstResource` (the other being :class:`Relationship`).

.. module:: flask_presst

The :func:`resource_method` decorator
-------------------------------------

.. autofunction:: resource_method


Request parsing with :func:`resource_method`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Methods decorated with :func:`resource_method` are wrapped into a :class:`ResourceAction`, which itself contains
a parser that is run whenever the method is called.

.. autoclass:: flask_presst.nesting.ResourceAction
   :members:

Example code
^^^^^^^^^^^^

.. code-block:: python

    class ArticleResource(ModelResource):

        class Meta:
            model = Article

        @resource_method('GET')
        def newer_than(self, article, other):
            """ GET /article/1/newer_than?other=/article/2 """
            return article.date_created < other.date_created

        newer_than.add_argument('other', type=field.ToOne('article'), required=True)

        @resource_method('GET', collection=True)
        def filter(self, articles, title, rating):
            """ GET /article/filter?title=Sensational&rating=5 """
            return self.marshal_item_list(
                        articles.filter(and_(Article.title.like('%{}%'.format(title)),
                                             Article.rating >= rating)))

        filter.add_argument('title', location='args', required=True)
        filter.add_argument('rating', location='args', default=0)


Return value marshalling
------------------------

Return values from a :func:`resource_method` can be marshalled using :func:`flask_restful.marshal_with`.
For example::

    @resource_method('GET')
    @marshal_with({'article': fields.ToOne('article'), 'num_comments': fields.Integer()})
    def num_comments(self, article):
        return {
            'article': article,
            'num_comments': len(article.comments)
        }

Because often-times a resource will only return a single field, such as an integer or a resource item, Flask-Presst
ships with an additional decorator, :class:`marshal_with_field`.


.. autoclass:: marshal_with_field

The :class:`marshal_with_field` decorator is used like this::

    @resource_method('GET')
    @marshal_with_field(fields.ToMany('ticket'))
    def completed(tickets):
        return tickets.filter(Ticket.status == 'complete')

.. note::

    When returning a large number of items from a specific resource directly from an `SQLAlchemy` query, it is best to
    use :meth:`PresstResource.marshal_item_list`, as this marshaling function will paginate the result while
    :class:`fields.ToMany` does not.
