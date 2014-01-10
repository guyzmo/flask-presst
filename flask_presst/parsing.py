import inspect
from flask.ext.restful import fields as restful_fields
from flask.ext.restful.reqparse import Argument
from flask_presst.fields import Array, KeyValue, JSON, Raw
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
                Array: list,
                KeyValue: dict,
                JSON: dict, # NOTE only works with request.json, not request.args.
                restful_fields.DateTime: datetime.datetime,
                restful_fields.String: six.text_type,
                restful_fields.Boolean: bool,
                restful_fields.Integer: int
            }[field.__class__]
        except KeyError:
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
                # TODO .date() if self.type is datetime.date.
                return iso8601.parse_date(value)

        try:
            return self.type(value, self.name, op)
        except TypeError:
            try:
                return self.type(value, self.name)
            except TypeError:
                return self.type(value)