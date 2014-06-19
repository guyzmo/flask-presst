"""
Contains some additional field types that are not included in Flask-RESTful.
"""
import datetime
from flask import current_app
from flask.ext.restful.fields import *
from jsonschema import ValidationError, validate
from jsonschema.validators import validator_for
from werkzeug.utils import cached_property
from flask_presst.references import Reference


class RelationshipField(Raw):
    def __init__(self, resource, embedded=False, relationship_name=None, *args, **kwargs):
        super(RelationshipField, self).__init__(*args, **kwargs)
        self.bound_resource = None
        self.resource = resource
        self.embedded = embedded
        self.relationship_name = None

    @cached_property
    def python_type(self):
        """
        A callable that converts a uri into a matching instance of type :attr:`resource_class`.
        """
        return Reference(self.resource_class)

    @cached_property
    def resource_class(self):
        """

        """
        if self.resource == 'self':
            return self.bound_resource
        return current_app.presst.get_resource_class(self.resource,
                                                     getattr(self.bound_resource, '__module__', None))


class ToMany(RelationshipField):
    """

    :param resource: resource class, resource name, or SQLAlchemy model
    :param bool embedded: whether to embed the whole items in the output (otherwise formats them as uris)
    """
    def format(self, item_list):
        marshal_fn = self.resource_class.item_get_resource_uri \
            if not self.embedded else self.resource_class.marshal_item

        return list(marshal_fn(item) for item in item_list)

    @cached_property
    def python_type(self):
        """
        A callable that converts a list of uris into instances of type :attr:`resource_class`.
        """
        reference = Reference(self.resource_class)
        return lambda values: [reference(value) for value in values]


class ToOne(RelationshipField):
    """

    :param resource: resource class, resource name, or SQLAlchemy model
    :param bool embedded: whether to embed the whole item in the output (otherwise formats it as uri)
    """
    def __init__(self, resource, embedded=False, required=False, *args, **kwargs):
        super(ToOne, self).__init__(resource, embedded, *args, **kwargs)
        self.required = required

    def format(self, item):
        if not self.embedded:
            return self.resource_class.item_get_resource_uri(item)
        return self.resource_class.marshal_item(item)


class Array(Raw):
    python_type = list


class KeyValue(Raw):
    python_type = dict


class JSON(Raw):
    """
    For passing through raw JSON data.

    :param dict schema: An optional `JSON schema <http://json-schema.org/>`_ for validation
    """

    def __init__(self, schema=None, *args, **kwargs):
        super(JSON, self).__init__(*args, **kwargs)

        if schema is not None:
            validator_class = validator_for(schema)
            validator_class.check_schema(schema)

            self.validator = validator_class(schema)
        else:
            self.validator = None

    def python_type(self, value):
        """
        :returns: value
        """
        if self.validator:
            try:
                self.validator.validate(value)  # NOTE only works with request.json, not request.args.
            except ValidationError as ve:
                raise TypeError("Failed validating '{}' in schema: {}".format(ve.validator, ve.schema))
        return value

class Date(Raw):
    """
    For formatting a field as an ISO 8601 date (i.e. YYYY-MM-DD).
    """
    python_type = datetime.date

    def format(self, value):
        return value.strftime('%Y-%m-%d')
