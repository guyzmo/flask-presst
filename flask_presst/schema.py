import inspect
from operator import itemgetter
from flask import json, current_app
from flask.views import View
from flask_presst.references import Reference
from flask_presst import fields
from flask_presst.resources import ModelResource
from flask_presst.routes import ResourceAction, Relationship


class HyperSchema(View):
    """
    Top-level JSON-Schema for the API.

    Attempts to stick to `JSON Hyper-Schema: Hypertext definitions for JSON Schema
     <http://json-schema.org/latest/json-schema-hypermedia.html>`_ although the current implementation may not yet be
    completely valid and is certainly not yet complete.
    """
    def __init__(self, api):
        self.api = api

    def dispatch_request(self):
        # TODO enforce Content-Type: application/schema+json (overwritten by Flask-RESTful)
        return self.api.schema, 200

