import inspect
from flask_restful import fields as restful_fields, abort
from flask_restful.reqparse import Argument
from flask_presst.utils.parsedate import parsedate_to_datetime
from iso8601 import iso8601
import datetime
import six


class PresstArgument(Argument):
    @staticmethod
    def _get_python_type_from_field(field):
        if hasattr(field, 'python_type'):
            return field.python_type

        try:
            return {
                restful_fields.DateTime: datetime.datetime,
                restful_fields.String: six.text_type,
                restful_fields.Boolean: bool,
                restful_fields.Integer: int
            }[field.__class__]
        except KeyError:  # pragma: no cover
            return six.text_type

    def convert(self, value, op):
        if isinstance(self.type, restful_fields.Raw):
            self.type = self._get_python_type_from_field(self.type)

        if inspect.isclass(self.type):
            # check if we're expecting a string and the value is `None`
            if value is None and issubclass(self.type, six.string_types):
                return None

            # handle date and datetime:
            if issubclass(self.type, datetime.date):
                try: # RFC822-formatted strings are now the default:
                    dt = parsedate_to_datetime(value)
                except TypeError: # ISO8601 fallback:
                    dt = iso8601.parse_date(value)

                if self.type is datetime.date:
                    return dt.date()
                return dt

        try:
            return self.type(value, self.name, op)
        except TypeError:
            try:
                return self.type(value, self.name)
            except TypeError:
                return self.type(value)


class ParsingException(Exception):

    def __init__(self, field=None, message=None):
        self.field = field
        self.message = message


class SchemaParser(object):

    def __init__(self, fields, required_fields=None, read_only_fields=None):  # TODO read-only fields
        self.fields = {key or field.attribute: field for key, field in fields.items()}
        self.required_fields = required_fields or []
        self.read_only_fields = read_only_fields or []

    @property
    def schema(self):
        return {
            'type': 'object',
            # TODO readOnly fields
            'properties': {key: field.schema for key, field in self.fields.items()},
            'required': self.required_fields or []
        }

    def parse(self, obj, partial=False, resolve=None):
        """
        :param obj: JSON-object to parse
        :param bool partial: Whether to allow omitting required fields
        :param dict resolve: An optional dictionary of properties to pre-fill rather than load from fields.
        """
        converted = dict(resolve) if resolve else {}

        try:
            for key, value in six.iteritems(obj):
                try:
                    field = self.fields[key]
                except KeyError:
                    raise ParsingException(message='Unknown field: {}'.format(key))
                    # TODO collect different exceptions.

                # NOTE silently ignoring read-only fields. This could throw an error.
                if key in self.read_only_fields:
                    continue
                    # raise ParsingException(message='Read-only field: {}'.format(key))

                # Handle old-style fields:
                if isinstance(field, restful_fields.Raw):
                    python_type = PresstArgument._get_python_type_from_field(field)
                    converted[key] = python_type(value)
                else:
                    field.validate(value)
                    converted[key] = field.convert(value)  # pass item

            if not partial:
                for key in self.required_fields:
                    if key not in converted:
                        raise ParsingException(message='Missing required field: {}'.format(key))

            return converted
        except ParsingException as e:
            abort(400, message=e.message)

