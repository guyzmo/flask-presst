
Resource Actions
================

`ResourceRoute` and `ResourceMultiRoute` allow you to define additional routes to a resource without having to define an entirely new
resource. The :func:`action` decorator is one way to very easily attach new route logic to a collection or item.
:class:`Resource` (the other being :class:`Relationship`).

.. module:: flask_presst

The :func:`action` decorator
----------------------------

.. autofunction:: action

Additionally, :func:`route` is a cousin of :func:`action` that does not attempt to access any items or collection of
items of the resource and is hence more suitable when access to neither is needed.

Request parsing with :func:`action`
-----------------------------------


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

Return values from a :func:`action` or :func:`route` can be marshalled with the ``response_property`` attribute.

For example::

    @action('GET', response_property=fields.Nested({
        'article': fields.ToOne('article'),
        'num_comments': fields.Integer()
    }))
    def num_comments(self, article):
        return {
            'article': article,
            'num_comments': len(article.comments)
        }

It is also possible to simply use ``marshal_with``, but this will not generate a ``targetSchema`` entry in the documentation.

Python 3 function annotations
-----------------------------

When developing exclusively for Python 3.x it is possible to use function annotations to specify parser arguments:

.. code-block:: python

        @action('GET', collection=True)
        def filter(self,
                   articles,
                   title: fields.String(nullable=False),
                   rating: field.Integer(default=0)) -> fields.Many('article'):
            return articles.filter(and_(Article.title.like('%{}%'.format(title)),
                                        Article.rating >= rating))