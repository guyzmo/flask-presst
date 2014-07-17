from functools import wraps

from flask_restful import unpack

from flask_presst.api import PresstApi
from flask_presst.resources import Resource, ModelResource, PolymorphicModelResource
from flask_presst.routes import Relationship, action
from flask_presst.parse import SchemaParser
from flask_presst.references import ResourceRef


__all__ = (
    'PresstApi',
    'Resource',
    'ModelResource',
    'PolymorphicModelResource',

    'Relationship',
    'action',

    'SchemaParser',
    'ResourceRef',

    'marshal_with_field',

    'fields',
    'signals',
)


class marshal_with_field(object):
    """
    A decorator that formats the return values of your methods using a single field.

    >>> from flask_presst import marshal_with_field, fields
    >>> @marshal_with_field(fields.List(fields.Integer))
    ... def get():
    ...     return ['1', 2, 3.0]
    ...
    >>> get()
    [1, 2, 3]
    """
    def __init__(self, field):
        """
        :param field: a single field with which to marshal the output.
        """
        if isinstance(field, type):
            self.field = field()
        else:
            self.field = field

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            resp = f(*args, **kwargs)

            if isinstance(resp, tuple):
                data, code, headers = unpack(resp)
                return self.field.format(data), code, headers
            return self.field.format(resp)

        return wrapper