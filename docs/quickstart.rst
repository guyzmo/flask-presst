.. _Quickstart:

==========
Quickstart
==========

A Minimal API
-------------

A minimal Flask-Presst API looks like this:


.. literalinclude:: ../examples/quickstart_api_simple.py


Save this as `api.py` and run it using your Python interpreter. The application will create an in-memory SQLite
database, so the state of the application will reset every time the server is restarted.

.. code-block:: bash

    $ python api.py
     * Running on http://127.0.0.1:5000/


Let's make some requests to our new api using the excellent `HTTPie <http://httpie.org>`_ tool:

.. code-block:: bash

    $ http GET localhost:5000/book

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 2
    Content-Type: application/json
    Date: Mon, 31 Mar 2014 08:12:59 GMT
    Link: </book?page=1&per_page=20>; rel="self"
    Server: Werkzeug/0.9.4 Python/2.7.5

    []

.. code-block:: bash

    $ http -v POST localhost:5000/book title="On the Origin of Species" year_published:=1859

.. code-block:: http

    POST /book HTTP/1.1
    Accept: application/json
    Accept-Encoding: gzip, deflate, compress
    Content-Length: 63
    Content-Type: application/json; charset=utf-8
    Host: localhost:5000
    User-Agent: HTTPie/0.7.2

    {
        "title": "On the Origin of Species",
        "year_published": 1859
    }

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 88
    Content-Type: application/json
    Date: Mon, 31 Mar 2014 08:14:50 GMT
    Server: Werkzeug/0.9.4 Python/2.7.5

    {
        "_uri": "/book/1",
        "title": "On the Origin of Species",
        "year_published": 1859
    }

.. module:: flask_presst


:class:`Meta` class attributes
------------------------------

The :class:`Meta` class is how the basic functions of a resource are defined. Besides ``model``, there
are a few other properties that control how the :class:`ModelResource` maps to the SQLAlchemy model:

=====================  ==============================================================================
Attribute name         Description
=====================  ==============================================================================
model                  The `Flask-SQLAlchemy` model
resource_name          Defaults to the lower-case of the `model's` class name
id_field               Defaults to the name of the primary key of `model`.
include_fields         A list of fields that should be imported from the `model`. By default, all
                       columns other than foreign key and primary key columns are imported.
                       :func:`sqlalchemy.orm.relationship` model attributes and hybrid properties
                       cannot be defined in this way and have to be specified explicitly as resource
                       class attributes.
exclude_fields         A list of fields that should not be imported from the `model`.
exclude_polymorphic    Whether to exclude fields that are inherited from the parent model of a
                       polymorphic model. *Defaults to False*
required_fields        Fields that are automatically imported from the model are automatically
                       required if their columns are not `nullable` and do not have a `default`.
read_only_fields       A list of fields that are returned by the resource but are ignored in `POST`
                       and `PATCH` requests. Useful for e.g. timestamps.
title                  JSON-schema title declaration
description            JSON-schema description declaration
=====================  ==============================================================================


Relationships
-------------

Let's try to take our application a bit further. We'll add an Author model and create a relationship between Author
and Book.

.. literalinclude:: ../examples/quickstart_api_relationship.py

There are two ways to link between resources in Flask-Presst – using fields or using :class:`Relationship`:

- For each field, the API creates a new attribute in the item with the `resource uri` or `uris` of the related resource
  items. If a field is *embedded*, it does not include a uri, but instead includes a copy of the whole item.
- A :class:`Relationship` does not create any new attributes in the resource item. Instead it creates a new route.

So in our example each `book` item contains a copy of its author, and all books by each author can be retrieved
at `/author/<id>/books`.

.. code-block:: bash

    $ http POST localhost:5000/author first_name=Charles last_name=Darwin

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 77
    Content-Type: application/json
    Date: Mon, 31 Mar 2014 08:16:25 GMT
    Server: Werkzeug/0.9.4 Python/2.7.5

    {
        "first_name": "Charles",
        "last_name": "Darwin",
        "_uri": "/author/1"
    }

.. code-block:: bash

    $ http POST localhost:5000/book title="On the Origin of Species" author=/author/1

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 174
    Content-Type: application/json
    Date: Mon, 31 Mar 2014 08:17:03 GMT
    Server: Werkzeug/0.9.4 Python/2.7.5

    {
        "author": {
            "first_name": "Charles",
            "last_name": "Darwin",
            "_uri": "/author/1"
        },
        "_uri": "/book/1",
        "title": "On the Origin of Species",
        "year_published": null
    }


.. code-block:: bash

    $ http localhost:5000/author/1/books


.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 176
    Content-Type: application/json
    Date: Mon, 31 Mar 2014 08:17:42 GMT
    Link: </author/1/books?page=1&per_page=20>; rel="self"
    Server: Werkzeug/0.9.4 Python/2.7.5

    [
        {
            "author": {
                "first_name": "Charles",
                "last_name": "Darwin",
                "_uri": "/author/1"
            },
            "_uri": "/book/1",
            "title": "On the Origin of Species",
            "year_published": null
        }
    ]

.. note::

    The :class:`ToOne` and :class:`ToMany` fields have to be declared manually by adding them as attributes to
    the resource class – they are not imported from the model the way columns are. Other types of fields can be added in
    this manner as well. That means you can declare a custom property on a model class and add a matching field
    attribute to your resource.

Bulk operations
---------------

Flask-Presst supports two kinds of bulk operations: embedded resources and multiple-resource creation. Any resource that
is embedded as `ToOne` or `ToMany` field can be created through an embedded operation:

.. code-block:: bash

    $ echo '{"title": "Foo", "author": {"first_name":"Foo", "last_name":"Bar"}}' | http POST localhost:5000/book

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 133
    Content-Type: application/json
    Date: Thu, 17 Jul 2014 13:20:17 GMT
    Server: Werkzeug/0.9.4 Python/3.4.0

    {
        "_uri": "/book/1",
        "author": {
            "_uri": "/author/1",
            "first_name": "Foo",
            "last_name": "Bar"
        },
        "title": "Foo",
        "year_published": null
    }

Multiple items can be submitted in a create or delete operation by sending an array of items. The items will only
be created if validation of all of them succeeds. The same also works with update operations, as long as the items
being updated contain the ``_uri`` field.

.. code-block:: bash

    $ echo '[{"title": "Foo Vol I"}, {"title": "Foo Vol II"}]' | http POST localhost:5000/book

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 167
    Content-Type: application/json
    Date: Thu, 17 Jul 2014 13:34:48 GMT
    Server: Werkzeug/0.9.4 Python/3.4.0

    [
        {
            "_uri": "/book/1",
            "author": null,
            "title": "Foo Vol I",
            "year_published": null
        },
        {
            "_uri": "/book/2",
            "author": null,
            "title": "Foo Vol II",
            "year_published": null
        }
    ]

Pagination
----------

Items returned from any :class:`ModelResource` are paginated. Pagination in Flask-Presst works the same way as
`pagination in the GitHub API <http://developer.github.com/v3/#pagination>`_ works -- using the `Link` header and the
`page` and `per_page` query string arguments.

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 1732
    Content-Type: application/json
    Date: Sun, 30 Mar 2014 14:30:33 GMT
    Link: </book?page=1&per_page=20>; rel="self",
          </book?page=3&per_page=20>; rel="last",
          </book?page=2&per_page=20>; rel="next"
    Server: Werkzeug/0.9.4 Python/2.7.5


The default and maximum number of items per page can be configured using the
``'PRESST_DEFAULT_PER_PAGE'`` and ``'PRESST_MAX_PER_PAGE'`` configuration variables.


Resource actions
----------------

Finally, let's add some resource methods to our `BookResource`. Resource methods create additional routes, similar
to the way :class:`Relationship` does. The methods are defined using the :func:`action` decorator. They
each come with their own argument parser and their own route relative to the resource they are defined in.

We'll add two methods, ``/book/published_after?year={int}`` and ``/book/{id}/is_recent``:

.. code-block:: python

    class BookResource(ModelResource):
        author = fields.ToOne('author', embedded=True)

        @action('GET', collection=True)
        def published_after(self, books, year):
            return BookResource.marshal_item_list(
                books.filter(Book.year_published > year))

        published_after.add_argument('year', fields.Integer(), required=True)

        @action('GET')
        def is_recent(self, item):
            return datetime.date.today().year <= item.year_published + 10

        class Meta:
            model = Book


Now, we can create some new books and test the two methods:

.. code-block:: bash

    http POST localhost:5000/book title="On the Origin of Species" year_published:=1859 > /dev/null
    http POST localhost:5000/book title="The Double Helix" year_published:=1968 > /dev/null

.. code-block:: bash

    $ http -v GET localhost:5000/book/published_after year==1900

.. code-block:: http

    GET /book/published_after?year=1900 HTTP/1.1
    Accept: */*
    Accept-Encoding: gzip, deflate, compress
    Host: localhost:5000
    User-Agent: HTTPie/0.7.2


.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 98
    Content-Type: application/json
    Date: Mon, 31 Mar 2014 08:18:51 GMT
    Link: </book/published_after?page=1&per_page=20>; rel="self"
    Server: Werkzeug/0.9.4 Python/2.7.5

    [
        {
            "author": null,
            "_uri": "/book/2",
            "title": "The Double Helix",
            "year_published": 1968
        }
    ]


.. code-block:: bash

    $ http GET localhost:5000/book/2/is_recent

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 5
    Content-Type: application/json
    Date: Mon, 31 Mar 2014 08:20:00 GMT
    Server: Werkzeug/0.9.4 Python/2.7.5

    false

