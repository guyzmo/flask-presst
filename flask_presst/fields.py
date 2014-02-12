"""
Contains some additional field types that are not included in Flask-RESTful.
"""
from flask.ext.restful.fields import *
from werkzeug.utils import cached_property
from flask_presst.references import Reference


class RelationshipFieldBase(Raw):
    def __init__(self, resource, embedded=False, relationship_name=None, *args, **kwargs):
        super(RelationshipFieldBase, self).__init__(*args, **kwargs)
        self.bound_resource = None
        self._resource = resource
        self.embedded = embedded
        self.relationship_name = None

    @cached_property
    def python_type(self):
        return Reference(self.resource_class)

    @cached_property
    def resource_class(self):
        if self._resource == 'self':
            return self.bound_resource
        return self.bound_resource.api.get_resource_class(self._resource, self.bound_resource.__module__)


class ToMany(RelationshipFieldBase):
    def format(self, item_list):
        marshal_fn = self.resource_class.item_get_resource_uri \
            if not self.embedded else self.resource_class.marshal_item

        return list(marshal_fn(item) for item in item_list)

    @cached_property
    def python_type(self):
        return lambda values: map(Reference(self.resource_class), values)


class ToOne(RelationshipFieldBase):
    def __init__(self, resource, embedded=False, required=False, *args, **kwargs):
        super(ToOne, self).__init__(resource, embedded, *args, **kwargs)
        self.required = required

    def format(self, item):
        if not self.embedded:
            return self.resource_class.item_get_resource_uri(item)
        return self.resource_class.marshal_item(item)


class Array(Raw):
    pass


class KeyValue(Raw):
    pass


class JSON(Raw):
    pass


class Date(Raw):
    def format(self, value):
        return value.strftime('%Y-%m-%d')