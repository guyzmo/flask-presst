from functools import wraps
from flask.ext.restful import unpack
from flask_presst.api import PresstApi
from flask_presst.resources import PresstResource, ModelResource, PolymorphicModelResource
from flask_presst.nesting import Relationship, resource_method
from flask_presst.parsing import PresstArgument
from flask_presst.references import Reference


__all__ = (
    'PresstApi',
    'PresstResource',
    'ModelResource',
    'PolymorphicModelResource',

    'Relationship',
    'resource_method',

    'PresstArgument',
    'Reference',
    'marshal_with_field',

    'fields',
    'signals',
)


class marshal_with_field(object):
    """
    A decorator that formats the return values of your methods using a single field.

    >>> from flask.ext.presst import marshal_with_field, fields
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