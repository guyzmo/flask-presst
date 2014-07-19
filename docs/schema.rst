
JSON Hyper-Schema
=================

.. versionadded:: 0.2.5

Flask-Presst is self-documenting, documented using `JSON Hyper-Schema <http://json-schema.org/latest/json-schema-hypermedia.html>`_.
The schema index lives at ``{api_prefix}/schema`` and resource schemas live at ``{api_prefix}/{resource}/schema``.

An example schema is shown below:

.. code-block:: bash

    $ http localhost:5000/schema

.. code-block:: http

    HTTP/1.0 200 OK
    Content-Length: 353
    Content-Type: application/json
    Date: Thu, 17 Jul 2014 13:12:13 GMT
    Server: Werkzeug/0.9.4 Python/3.4.0

    {
        "$schema": "http://json-schema.org/draft-04/hyper-schema#",
        "definitions": {
            "_pagination": {
                "properties": { }
            }
        },
        "properties": {
            "author": {
                "$ref": "/author/schema#"
            },
            "book": {
                "$ref": "/book/schema#"
            }
        }
    }
