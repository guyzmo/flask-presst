import datetime
from flask.ext.restful import fields
from flask.ext.presto.fields import ArrayField, KeyValueField, JSONField, BaseRelationshipField
from flask.ext.presto.references import ItemType


def _item_ref_for_resource(resource):
    class ItemRef(object):
        resource = resource
        def __init__(self, resource_uri):
            print resource_uri + self.resource + '_resolved'
    return ItemRef


def _get_python_type_from_field(field):
    if isinstance(field, BaseRelationshipField):
        return ItemType(field._resource_class)
    if isinstance(field, ArrayField):
        return list
    if isinstance(field, KeyValueField) or isinstance(field, JSONField):
        return dict
    return unicode


def _get_field_from_python_type(python_type):
    return {
        str: fields.String,
        unicode: fields.String,
        int: fields.Integer,
        bool: fields.Boolean,
        list: ArrayField,
        dict: KeyValueField,
        datetime.date: fields.DateTime,
        datetime.datetime: fields.DateTime # TODO extend with JSON, dict (HSTORE) etc.
    }[python_type]

