# from iso8601 import iso8601
import aniso8601
from flask_restful.fields import get_value
from jsonschema import Draft4Validator, ValidationError, FormatChecker
from werkzeug.utils import cached_property

from flask_presst.references import ResourceRef


class Raw(object):
    def __init__(self, schema, default=None, attribute=None, nullable=True):
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
                if not any('null' in choice.get('type', []) for choice in schema['oneOf']):
                    schema['oneOf'].append({'type': 'null'})
            else:
                type_ = schema.get('type')

                if type_ is not None and 'null' not in type_:
                    if isinstance(type_, (str, dict)):
                        schema['type'] = [type_, 'null']
                    else:
                        schema['type'].append('null')

        if self.default:
            schema['default'] = self.default

        # Draft4Validator.check_schema(schema)

        return schema

    @cached_property
    def _validator(self):
        Draft4Validator.check_schema(self.schema)
        return Draft4Validator(self.schema, format_checker=FormatChecker())

    def validate(self, value):
        try:
            self._validator.validate(value)
        except ValidationError as ve:
            raise ValueError("Failed validating '{}' in schema: {}".format(ve.validator, ve.schema))

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

    def output(self, key, obj):
        """Pulls the value for the given key from the object, applies the
        field's formatting and returns the result.
        :exception MarshallingException: In case of formatting problem
        """
        value = get_value(key if self.attribute is None else self.attribute, obj)

        if value is None:
            return self.default

        return self.format(value)

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


class Arbitrary(Raw):
    def __init__(self, **kwargs):
        super(Arbitrary, self).__init__({}, **kwargs)


JSON = Arbitrary


class Object(Raw):
    def __init__(self, **kwargs):
        super(Object, self).__init__({"type": "object"}, **kwargs)


class String(Raw):
    def __init__(self, **kwargs):
        super(String, self).__init__({"type": "string"}, **kwargs)


class Integer(Raw):
    # TODO minValue and maxValue optional arguments
    def __init__(self, default=0, minimum=None, maximum=None, **kwargs):
        schema = {"type": "integer"}

        if minimum is not None:
            schema['minimum'] = minimum
        if maximum is not None:
            schema['maximum'] = maximum

        super(Integer, self).__init__(schema, default=default, **kwargs)

    def format(self, value):
        return int(value)


class PositiveInteger(Integer):
    def __init__(self, default=0, maximum=None, **kwargs):
        super(PositiveInteger, self).__init__(default, minimum=0, maximum=maximum, **kwargs)


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
        if value is None:
            return []
        return [self.container.format(v) for v in value]

    def convert(self, value):
        if value is None:
            return []
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
# class ResourceUriBase(Raw):
#     pass

class EmbeddedBase(object):
    pass

class ToOne(Raw, EmbeddedBase):
    def __init__(self, resource, relationship_name=None, embedded=False, **kwargs):
        self._resource = ref = ResourceRef(resource)
        self.relationship_name = relationship_name
        self.bound_resource = None
        self.embedded = embedded

        def make_schema():
            resource = ref.resolve()
            return {
                "oneOf": [
                    {'$ref': '/{}/schema#/definitions/_uri'.format(resource.resource_name)},
                    {'$ref': '/{}/schema#'.format(resource.resource_name)}
                ]
            }

        super(ToOne, self).__init__(make_schema, **kwargs)

    @cached_property
    def resource(self):
        if self._resource.reference_str == 'self':
            return self.bound_resource
        return self._resource.resolve()

    def validate(self, value):
        if value is None and not self.nullable:
            raise ValueError('Reference is not nullable')

        # TODO proper validation (now fails in convert step)

    def format(self, item):
        if not self.embedded:
            return self.resource.item_get_uri(item)
        return self.resource.marshal_item(item)

    def convert(self, value, commit=False):
        # value is one of:
        # resource uri -> attempt to load document with that uri
        # object matching schema -> create new document with that uri (needs to be appended to session/request somehow (g object or with object?))
        # object matching schema with resource uri field -> load document and update it
        if value is None:
            return None

        return self.resource.resolve_item(value, create=True, update=True, commit=commit)


class ToMany(List, EmbeddedBase):
    def __init__(self, resource, relationship_name=None, embedded=False, **kwargs):
        super(ToMany, self).__init__(ToOne(resource, embedded=embedded), **kwargs)
        self.relationship_name = relationship_name

    def validate(self, value):
        if value is None and not self.nullable:
            raise ValueError('Reference is not nullable')

        # TODO proper validation (now fails in convert step)

class ToManyKV(KeyValue, EmbeddedBase):
    def __init__(self, resource, relationship_name=None, embedded=False, **kwargs):
        super(ToManyKV, self).__init__(ToOne(resource, embedded=embedded), **kwargs)
        self.relationship_name = relationship_name

    def validate(self, value):
        if value is None and not self.nullable:
            raise ValueError('Reference is not nullable')

        # TODO proper validation (now fails in convert step)
