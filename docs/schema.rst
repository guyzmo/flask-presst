
Schema
======

.. versionadded:: 0.2.5

The schema view is an additional view that lives in the root of the API and when enabled returns a schema of all
resources, resource methods and relationships in the API in the
`JSON Hyper-Schema <http://json-schema.org/latest/json-schema-hypermedia.html>`_ format.

Since the schema is experimental, it has to be enabled manually by calling ``api.enable_schema()``.

.. code-block:: python

    api = PresstApi()
    # api.add_resource(...)
    # api.add_resource(...)
    # api.add_resource(...)
    api.enable_schema()


An example schema of the API from the :ref:`Quickstart`:

.. code-block:: json

    {
        "$schema": "http://json-schema.org/hyper-schema#",
        "definitions": {
            "book": {
                "definitions": {
                    "resource_uri": {
                        "format": "uri",
                        "readOnly": true,
                        "type": "string"
                    },
                    "title": {
                        "type": "string"
                    }
                },
                "links": [
                    {
                        "href": "/book/{id}",
                        "rel": "self"
                    }
                ],
                "properties": {
                    "resource_uri": {
                        "$ref": "#/definitions/book/definitions/resource_uri"
                    },
                    "title": {
                        "$ref": "#/definitions/book/definitions/title"
                    }
                },
                "required": [
                    "title"
                ]
            }
        },
        "properties": {
            "book": {
                "$ref": "#/definitions/book"
            }
        }
    }
