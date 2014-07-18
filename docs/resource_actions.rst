
Resource Actions
================

`ResourceRoute` allow you to define additional routes to a resource without having to define an entirely new
resource. The :func:`action` decorator is one way to very easily attach new route logic to a collection or item.
:class:`Resource` (the other being :class:`Relationship`).

.. module:: flask_presst

The :func:`action` decorator
-------------------------------------

.. autofunction:: action


Request parsing with :func:`action`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Methods decorated with :func:`action` are wrapped into a :class:`ResourceAction`, which parses requests to that route
using a specified list of fields.

.. autoclass:: flask_presst.routes.ResourceAction
   :members:

Example code
^^^^^^^^^^^^

.. code-block:: python

    class ArticleResource(ModelResource):

        class Meta:
            model = Article

        @action('GET')
        def newer_than(self, article, other):
            """ GET /article/1/newer_than?other=/article/2 """
            return article.date_created < other.date_created

        newer_than.add_argument('other', field.ToOne('article', nullable=False))

        @action('GET', collection=True)
        def filter(self, articles, title, rating):
            """ GET /article/filter?title=Sensational&rating=5 """
            return self.marshal_item_list(
                        articles.filter(and_(Article.title.like('%{}%'.format(title)),
                                             Article.rating >= rating)))

        filter.add_argument('title', fields.String(nullable=False))
        filter.add_argument('rating', field.Integer(default=0))



Return value marshalling
------------------------

Return values from a :func:`action` can be marshalled using :func:`flask_restful.marshal_with`.
For example::

    @action('GET')
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

    @action('GET')
    @marshal_with_field(fields.ToMany('ticket'))
    def completed(tickets):
        return tickets.filter(Ticket.status == 'complete')

.. note::

    When returning a large number of items from a specific resource directly from an `SQLAlchemy` query, it is best to
    use :meth:`Resource.marshal_item_list`, as this marshaling function will paginate the result while
    :class:`fields.ToMany` does not.


Python 3 function annotations
-----------------------------

When developing exclusively for Python 3.x it is possible to use function annotations to specify parser attributes:

.. code-block:: python

        @action('GET', collection=True)
        def filter(self,
                   articles,
                   title: fields.String(nullable=False),
                   rating: field.Integer(default=0)) -> fields.ToMany('article'):
            return self.marshal_item_list(
                        articles.filter(and_(Article.title.like('%{}%'.format(title)),
                                             Article.rating >= rating)))


.. note::

    Note that the `return type` function annotation is optional and not currently used for marshalling, but only to generate the
    ``targetSchema`` property in the schema definition. In Python 2.7, it can be set through ``ResourceAction.target_schema``.