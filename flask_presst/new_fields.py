# from iso8601 import iso8601
import aniso8601
from flask import g
from jsonschema import Draft4Validator, ValidationError, FormatChecker
import six
from werkzeug.utils import cached_property
from flask.ext.presst.references import ResourceRef, ItemWrapper


class Raw(object):
    def __init__(self, schema, default=None, attribute=None, nullable=False):
        self._schema = schema
        self.default = default
        self.attribute = attribute
        self.nullable = nullable

        if isinstance(schema, dict) and 'null' in schema.get('type', []):
            self.nullable = True

    @cached_property
    def schema(self):
        if callable(self._schema):
            schema = self._schema()
        else:
            schema = dict(self._schema)

        if self.nullable:
            if "oneOf" in schema:
                if not any('null' in o.get('type') for o in schema['oneOf']):
                    schema['oneOf'].append({'type': 'null'})
            else:
                type_ = schema['type']

                if 'null' not in type_:
                    if isinstance(type_, (str, dict)):
                        schema['type'] = [type_, 'null']
                    else:
                        schema['type'].append('null')

        # Draft4Validator.check_schema(schema)

        return schema

    def validate(self, value):
        Draft4Validator(self.schema, format_checker=FormatChecker()).validate(value)

    def is_valid(self, value):
        try:
            self.validate(value)
        except ValidationError:
            return False
        return True

    def parse(self, value):
        """

        .. note::

            It is encouraged to override this method with validation methods that are more efficient
            than the :mod:`jsonschema` implementation.

        :raises TypeError: when validation fails
        :raises HttpException: when a lookup of an associated resource fails
        """
        self.validate(value)
        return self.convert(value)

    def format(self, value):
        """
        Format a Python value representation for output in JSON; noop by default.
        """
        return value

    def convert(self, value):
        """
        Convert a JSON value representation to a Python object; noop by default.
        """
        return value


class Custom(Raw):
    def __init__(self, schema, converter=None, formatter=None, **kwargs):
        super(Custom, self).__init__(schema, **kwargs)
        self.converter = converter
        self.formatter = formatter

    def format(self, value):
        if self.formatter is None:
            return value
        return self.formatter(value)

    def convert(self, value):
        if self.converter is None:
            return value
        return self.converter(value)


class Object(Raw):
    def __init__(self, **kwargs):
        super(Object, self).__init__({"type": "object"}, **kwargs)


class String(Raw):
    def __init__(self, **kwargs):
        super(String, self).__init__({"type": "string"}, **kwargs)


class Integer(Raw):
    # TODO minValue and maxValue optional arguments
    def __init__(self, default=0, **kwargs):
        super(Integer, self).__init__({"type": "integer"}, **kwargs)

    def format(self, value):
        return int(value)


class Number(Raw):
    # TODO minValue and maxValue optional arguments
    def __init__(self, default=0, **kwargs):
        super(Number, self).__init__({"type": "number"}, **kwargs)


class Boolean(Raw):
    def __init__(self, default=0, **kwargs):
        super(Boolean, self).__init__({"type": "boolean"}, **kwargs)

    def format(self, value):
        return bool(value)


class Date(Raw):
    def __init__(self, **kwargs):
        # TODO is a 'format' required for "date"
        super(Date, self).__init__({"type": "string", "format": "date"}, **kwargs)

    def format(self, value):
        return value.strftime('%Y-%m-%d')

    def convert(self, value):
        return aniso8601.parse_date(value)


class DateTime(Raw):

    def __init__(self, **kwargs):
        super(DateTime, self).__init__({"type": "string", "format": "date-time"}, **kwargs)

    def format(self, value):
        # TODO needs improving. Always export with 'Z'
        return '{}Z'.format(value.isoformat())

    def convert(self, value):
        # FIXME enforce UTC
        return aniso8601.parse_datetime(value)


class Uri(Raw):
    def __init__(self, **kwargs):
        super(Uri, self).__init__({"type": "string", "format": "uri"}, **kwargs)


class Email(Raw):
    def __init__(self, **kwargs):
        super(Email, self).__init__({"type": "string", "format": "email"}, **kwargs)


class List(Raw):
    def __init__(self, cls_or_instance, **kwargs):
        if isinstance(cls_or_instance, type):
            # if not issubclass(cls_or_instance, Raw):
            #     raise RuntimeError('KeyValue ...')
            self.container = cls_or_instance()
        else:
            # if not isinstance(cls_or_instance, Raw):
            #     raise MarshallingException(error_msg)
            self.container = cls_or_instance

        container = self.container

        if isinstance(container, Raw):
            super(List, self).__init__(lambda: {
                "type": "array",
                "items": container.schema
            }, **kwargs)

    def format(self, value):
        return [self.container.format(v) for v in value]

    def convert(self, value):
        return [self.container.convert(v) for v in value]


class KeyValue(Raw):
    def __init__(self, cls_or_instance, **kwargs):
        if isinstance(cls_or_instance, type):
            # if not issubclass(cls_or_instance, Raw):
            #     raise RuntimeError('KeyValue ...')
            self.container = cls_or_instance()
        else:
            # if not isinstance(cls_or_instance, Raw):
            #     raise MarshallingException(error_msg)
            self.container = cls_or_instance

        container = self.container

        if isinstance(container, Raw):
            super(KeyValue, self).__init__(lambda: {
                "type": "object",
                "additionalProperties": container.schema
            }, **kwargs)

    def format(self, value):
        return {k: self.container.format(v) for k, v in value.items()}

    def convert(self, value):
        return {k: self.container.convert(v) for k, v in value.items()}


#
# class ResourceUri(Raw):
#     pass

class ToOne(Raw):
    def __init__(self, resource, embedded=True, **kwargs):
        self._resource = ref = ResourceRef(resource)
        self.embedded = embedded

        def make_schema():
            resource = ref.resolve()
            return {
                "oneOf": [
                    {
                        "type": "string",
                        "format": "uri",
                        "pattern": resource.instance_uri_pattern
                    },

                    #TODO reference using $ref.

                    {
                        "type": "object",
                        "properties": {
                            "_uri": {
                                "type": "string",
                                "format": "uri",
                                "pattern": resource.instance_uri_pattern
                            }
                        },
                        "required": ["_uri"]
                    },
                    resource.schema
                ]
            }

        super(ToOne, self).__init__(make_schema, **kwargs)

    @cached_property
    def resource(self):
        return self._resource.resolve()

    def format(self, item):
        if not self.embedded:
            return self.resource.item_get_resource_uri(item)
        return self.resource.marshal_item(item)

    def convert(self, value):
        # value is one of:
        # resource uri -> attempt to load document with that uri
        # object matching schema -> create new document with that uri (needs to be appended to session/request somehow (g object or with object?))
        # object matching schema with resource uri field -> load document and update it
        if value is None:
            return None

        resource_uri = None
        request_data = None

        if isinstance(value, six.text_type):
            resource_uri = value
        elif isinstance(value, dict):
            if '_uri' in value:
                request_data = dict(value)
                resource_uri = request_data.pop('_uri')
            else:
                request_data = value

        if resource_uri:
            resource, id = self.resource.api.parse_resource_uri(value)

            if self.resource != resource:
                raise ValueError('Wrong resource item type, expected {0}, got {1}'.format(
                    self.resource.resource_name,
                    resource.resource_name))

            return self.resource.request_make_item(id, data=request_data)
        else:
            return self.resource.request_make_item(data=request_data)


class ToMany(List):
    def __init__(self, resource, **kwargs):
        super(ToMany, self).__init__(ToOne(resource), **kwargs)


class ToManyKV(KeyValue):
    def __init__(self, resource, **kwargs):
        super(ToManyKV, self).__init__(ToOne(resource), **kwargs)
