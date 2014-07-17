
from flask import request
from flask_restful import abort


class ParsingException(Exception):

    def __init__(self, field=None, message=None):
        self.field = field
        self.message = message


class SchemaParser(object):

    def __init__(self, fields=None, required_fields=None, read_only_fields=None):  # TODO read-only fields
        if fields is None:
            fields = {}
        self.fields = {key or field.attribute: field for key, field in fields.items()}
        self.required_fields = set(required_fields or [])
        self.read_only_fields = set(read_only_fields or [])

    def add(self, name, field, required=True):
        self.fields[name] = field
        if required:
            self.required_fields.add(name)

    @property
    def schema(self):
        schema = {
            'type': 'object',
            # TODO readOnly fields properly designated
            'properties': {key: field.schema for key, field in self.fields.items() if key not in self.read_only_fields},
        }

        if self.required_fields:
            schema['required'] = list(self.required_fields)

        return schema

    def parse_request(self):
        # TODO depending on request method switch between request.json and request.args (GET)
        # TODO alternatively: support both, with json taking priority
        request_data = request.json

        if not request_data and request.method in ('GET', 'HEAD'):
            request_data = request.args

        # on empty requirements, allow None:
        if not self.fields and not request_data:
            return {}

        if not isinstance(request_data, dict):
            abort(400, message='JSON dictionary required in the request body')

        return self.parse(request_data, partial=False)


    def parse(self, obj, partial=False, resolve=None, strict=False):
        """
        :param obj: JSON-object to parse
        :param bool partial: Whether to allow omitting required fields
        :param dict resolve: An optional dictionary of properties to pre-fill rather than load from fields.
        """
        converted = dict(resolve) if resolve else {}

        try:
            for key, field in self.fields.items():
                # NOTE silently ignoring read-only fields. This could throw an error.
                if key in self.read_only_fields:
                    continue
                    # abort(message='Read-only field: {}'.format(key))

                # ignore fields that have been pre-resolved
                if key in converted:
                    continue

                value = None

                try:
                    value = obj[key]
                    field.validate(value)

                except ValueError as e:
                    raise ParsingException('Invalid field: {}; {}'.format(key, e.args[0]))
                except KeyError:
                    if partial:
                        continue

                    # TODO required fields is somewhat redundant (eq. to default or nullable), what to do?

                    if field.default:
                        value = field.default
                    elif field.nullable:
                        value = None
                    elif key not in self.required_fields and not strict:
                        value = None
                    else:
                        raise ParsingException(message='Missing required field: {}'.format(key))

                converted[key] = field.convert(value)

            if strict:
                unknown_fields = set(obj.keys()) - set(self.fields.keys())
                if unknown_fields:
                    raise ParsingException('Unknown field(s): {}'.format(','.join(unknown_fields)))

            return converted

        except ParsingException as e:
            abort(400, message=e.message)