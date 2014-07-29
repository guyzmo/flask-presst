from functools import wraps
import aniso8601
from flask import current_app, url_for
from flask_restful.fields import get_value
from jsonschema import Draft4Validator, ValidationError, FormatChecker
from werkzeug.utils import cached_property

from flask_presst.references import ResourceRef, resolve_item


def skip_none(fn):
    @wraps(fn)
    def wrapper(self, value):
        if value is None:
            return None
        return fn(self, value)
    return wrapper


class Raw(object):
    """

    :param schema: JSON-schema for field, or :class:`callable` resolving to a JSON-schema when called
    :param default: optional default value, must be JSON-convertable
    :param attribute: key on parent object, optional.
    :param nullable: nullable
    """
    python_type = None

    def __init__(self, schema, default=None, attribute=None, nullable=True):
        self._schema = schema
        self.default = default
        self.attribute = attribute
        self.nullable = nullable

        if isinstance(schema, dict) and 'null' in schema.get('type', []):
            self.nullable = True

    @cached_property
    def schema(self):
        """
        JSON schema representation
        """
        if callable(self._schema):
            schema = self._schema()
        else:
            schema = dict(self._schema)

        if self.nullable:
            if "anyOf" in schema:
                if not any('null' in choice.get('type', []) for choice in schema['anyOf']):
                    schema['anyOf'].append({'type': 'null'})
            elif "oneOf" in schema:
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
        return Draft4Validator(self.schema,
                               format_checker=FormatChecker(),
                               resolver=current_app.presst.resolver_instance)

    def validate(self, value):
        """
        Validate ``value`` using ``schema``

        :raises ValueError: if validation fails
        """
        try:
            self._validator.validate(value)
        except ValidationError as ve:
            raise ValueError("Failed validating '{}' in schema: {}".format(ve.validator, ve.schema))

    def parse(self, value):
        """
        Validate and convert ``value``

        .. note::

            It is encouraged to override this method with validation methods that are more efficient
            than the :mod:`jsonschema` implementation.

        :raises TypeError: when validation fails
        :raises HttpException: when a lookup of an associated resource fails
        :returns: converted value
        """
        self.validate(value)
        return self.convert(value)

    def format(self, value):
        """
        Format a Python value representation for output in JSON. Noop by default.
        """
        return value

    def convert(self, value):
        """
        Convert a JSON value representation to a Python object. Noop by default.
        """
        return value

    def output(self, key, obj):
        """Pulls the value for the given key from the object, applies the
        field's formatting and returns the result.

        :raises MarshallingException: In case of formatting problem
        """
        value = get_value(key if self.attribute is None else self.attribute, obj)

        if value is None:
            return self.default

        return self.format(value)


class Custom(Raw):
    """

    :param dict schema: JSON-schema
    :param callable converter: convert function
    :param callable formatter: format function
    """
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
    """
    Accept any JSON value.
    """
    def __init__(self, **kwargs):
        super(Arbitrary, self).__init__({}, **kwargs)


JSON = Arbitrary


class Object(Raw):
    def __init__(self, **kwargs):
        super(Object, self).__init__({"type": "object"}, **kwargs)


class String(Raw):
    """
    :param int min_length: minimum length of string
    :param int max_length: maximum length of string
    :param str pattern: regex pattern that string must match
    :param list enum: list of strings with enumeration
    """

    def __init__(self, min_length=None, max_length=None, pattern=None, enum=None, **kwargs):
        schema = {"type": "string"}

        for value, kw in ((min_length, 'minLength'), (max_length, 'maxLength'), (pattern, 'pattern'), (enum, 'enum')):
            if value is not None:
                schema[kw] = value

        super(String, self).__init__(schema, **kwargs)


class Integer(Raw):
    python_type = int

    # TODO minValue and maxValue optional arguments
    def __init__(self, minimum=None, maximum=None, **kwargs):
        schema = {"type": "integer"}

        if minimum is not None:
            schema['minimum'] = minimum
        if maximum is not None:
            schema['maximum'] = maximum

        super(Integer, self).__init__(schema, **kwargs)

    def format(self, value):
        return int(value)


class PositiveInteger(Integer):
    """
    Only accepts integers >=0.
    """
    def __init__(self, default=0, maximum=None, **kwargs):
        super(PositiveInteger, self).__init__(minimum=0, maximum=maximum, **kwargs)


class Number(Raw):
    python_type = float

    def __init__(self, default=0,
                 minimum=None,
                 maximum=None,
                 exclusive_minimum=False,
                 exclusive_maximum=False,
                 **kwargs):

        schema = {"type": "number"}

        if minimum is not None:
            schema['minimum'] = minimum
            if exclusive_minimum:
                schema['exclusiveMinimum'] = True

        if maximum is not None:
            schema['maximum'] = maximum
            if exclusive_maximum:
                schema['exclusiveMaximum'] = True

        super(Number, self).__init__(schema, **kwargs)

    @skip_none
    def format(self, value):
        return float(value)


class Boolean(Raw):
    python_type = lambda b: b in ('true', 'True', True, 1)

    def __init__(self, default=0, **kwargs):
        super(Boolean, self).__init__({"type": "boolean"}, **kwargs)

    @skip_none
    def format(self, value):
        return bool(value)


class Date(Raw):
    """
    Only accept ISO8601-formatted date strings.
    """

    def __init__(self, **kwargs):
        # TODO is a 'format' required for "date"
        super(Date, self).__init__({"type": "string", "format": "date"}, **kwargs)

    @skip_none
    def format(self, value):
        return value.strftime('%Y-%m-%d')

    @skip_none
    def convert(self, value):
        return aniso8601.parse_date(value)


class DateTime(Raw):
    """
    Only accept ISO8601-formatted date-time strings.
    """

    def __init__(self, **kwargs):
        super(DateTime, self).__init__({"type": "string", "format": "date-time"}, **kwargs)

    @skip_none
    def format(self, value):
        return value.isoformat()

    @skip_none
    def convert(self, value):
        # FIXME enforce UTC
        return aniso8601.parse_datetime(value)


class Uri(Raw):
    """
    Only accept URI-formatted strings.
    """
    def __init__(self, **kwargs):
        super(Uri, self).__init__({"type": "string", "format": "uri"}, **kwargs)


class Email(Raw):
    """
    Only accept Email-formatted strings.
    """
    def __init__(self, **kwargs):
        super(Email, self).__init__({"type": "string", "format": "email"}, **kwargs)


class Nested(Raw):
    """

    :param dict fields: dictionary of fields
    :param read_only: optional list or tuple with keys of fields that are read-only
    """

    def __init__(self, fields, read_only=None, **kwargs):
        self.fields = fields
        self.read_only = read_only or []

        def make_schema():
            properties = {}
            schema = {
                "type": "object",
                "properties": properties,
            #    "additionalProperties": False
            }

            for key, field in self.fields.items():
                properties[key] = field.schema

                if key in self.read_only:
                    properties[key]['readOnly'] = True

            return schema

        super(Nested, self).__init__(make_schema, **kwargs)

    @skip_none
    def format(self, obj):
        return {k: f.format(get_value(k, obj)) for k, f in self.fields.items()}

    @skip_none
    def convert(self, obj):
        return {k: f.convert(get_value(k, obj)) for k, f in self.fields.items() if k not in self.read_only}


class List(Raw):
    """
    Accept arrays of a given field type.

    :param Raw cls_or_instance: field class or instance
    """
    def __init__(self, cls_or_instance, **kwargs):
        # TODO add minItems, maxItems
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
    """
    Accept objects with properties of a given field type.

    :param Raw cls_or_instance: field class or instance
    :param str key_pattern: an optional regular expression that all keys must match
    """
    def __init__(self, cls_or_instance, key_pattern=None, **kwargs):

        # TODO add patternProperties
        if isinstance(cls_or_instance, type):
            # if not issubclass(cls_or_instance, Raw):
            #     raise RuntimeError('KeyValue ...')
            self.container = cls_or_instance()
        else:
            # if not isinstance(cls_or_instance, Raw):
            #     raise MarshallingException(error_msg)
            self.container = cls_or_instance

        container = self.container

        if key_pattern:
            schema = lambda: {
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {
                    key_pattern: container.schema
                }
            }
        else:
            schema = lambda: {
                "type": "object",
                "additionalProperties": container.schema
            }

        super(KeyValue, self).__init__(schema, **kwargs)

    def format(self, value):
        return {k: self.container.format(v) for k, v in value.items()}

    def convert(self, value):
        return {k: self.container.convert(v) for k, v in value.items()}


class EmbeddedBase(object):
    pass

class ToOne(Raw, EmbeddedBase):
    """
    Accept a reference to an item of a ``resource``.

    References can be formatted as one of these:

    - Item URI --- read item
    - Object with ``_uri`` property --- read item and update with remaining properties
    - Object without ``_uri`` property --- create new item with given properties

    :param resource: :class:`str` reference or :class:`Resource`
    :param bool embedded: embed whole object on output if ``True``, URI otherwise
    """
    def __init__(self, resource, embedded=False, **kwargs):
        self._resource = ref = ResourceRef(resource)
        self.embedded = embedded
        self.binding = None

        def make_schema():
            resource = ref.resolve()
            resource_url = url_for(resource.endpoint)
            return {
                "oneOf": [
                    {'$ref': '{}/schema#/definitions/_uri'.format(resource_url)},
                    {'$ref': '{}/schema#'.format(resource_url)}
                ]
            }

        super(ToOne, self).__init__(make_schema, **kwargs)

    @cached_property
    def resource(self):
        if self._resource.reference_str == 'self':
            return self.binding
        return self._resource.resolve()

    def validate(self, value):
        if value is None and not self.nullable:
            raise ValueError('Reference is not nullable')

        # TODO proper validation (now fails in convert step)

    @skip_none
    def format(self, item):
        if not self.embedded:
            return self.resource.item_get_uri(item)
        return self.resource.marshal_item(item)

    @skip_none
    def convert(self, value, commit=False):
        return resolve_item(self.resource, value, create=True, update=False, commit=commit)


class ToMany(List, EmbeddedBase):
    """
    Accept a list of items of a resource.
    """
    def __init__(self, resource, embedded=False, **kwargs):
        super(ToMany, self).__init__(ToOne(resource, embedded=embedded, nullable=False), **kwargs)


class ToManyKV(KeyValue, EmbeddedBase):
    """
    Accept a dictionary mapping to items of a resource.
    """
    def __init__(self, resource, embedded=False, **kwargs):
        super(ToManyKV, self).__init__(ToOne(resource, embedded=embedded, nullable=False), **kwargs)


class One(Raw, EmbeddedBase):
    """
    Like :class:`ToOne`, except that embedding is required for both input and output. Uri references
    are not valid and the field is not nullable by default.
    """
    def __init__(self, resource, attribute=None, nullable=False, **kwargs):
        self._resource = ref = ResourceRef(resource)
        self.binding = None

        def make_schema():
            resource = ref.resolve()
            resource_url = url_for(resource.endpoint)
            return {'$ref': '{}/schema#'.format(resource_url)}

        super(One, self).__init__(make_schema, nullable=nullable, **kwargs)

    @cached_property
    def resource(self):
        if self._resource.reference_str == 'self':
            return self.binding
        return self._resource.resolve()

    @skip_none
    def format(self, item):
        return self.resource.marshal_item(item)

    @skip_none
    def convert(self, value, commit=False):
        return resolve_item(self.resource, value, create=True, update=False, commit=commit)


class Many(List, EmbeddedBase):
    """
    Like :class:`ToMany`, except that embedding is required for both input and output. Uri references
    are not valid and the field is not nullable by default.
    """
    def __init__(self, resource, nullable=False, **kwargs):
        super(Many, self).__init__(One(resource, nullable=False), nullable=nullable, **kwargs)
