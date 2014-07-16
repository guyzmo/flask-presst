import inspect
from operator import itemgetter
from flask import json, current_app
from flask.views import View
from flask_presst.references import Reference
from flask_presst import fields
from flask_presst.resources import ModelResource
from flask_presst.routes import ResourceAction, Relationship


class HyperSchema(View):
    """
    Generates a JSON schema of all resources in the API.

    Attempts to stick to `JSON Hyper-Schema: Hypertext definitions for JSON Schema
     <http://json-schema.org/latest/json-schema-hypermedia.html>`_ although the current implementation may not yet be
    completely valid and is certainly not yet complete.
    """

    def __init__(self, api):
        self.api = api

    def _get_ref(self, resource, full=False):
        if full:
            return {'$ref': '#/definitions/{}'.format(resource.endpoint)}
        else:
            return {'$ref': '#/definitions/{}/definitions/_uri'.format(resource.endpoint)}

    def _get_field_type(self, field):

        if inspect.isclass(field):
            try:
                field_type = {
                    int: 'integer',
                    float: 'number',
                    dict: 'object',
                    list: 'object',
                    bool: 'boolean'
                }[field]
            except KeyError:
                field_type = 'string'

            return {'type': field_type}

        if isinstance(field, fields.List):
            return {
                'type': 'array',
                'items': self._get_field_type(field.container)
            }
        elif isinstance(field, fields.Date):
            return {'type': 'string', 'format': 'date'}
        elif isinstance(field, fields.DateTime):
            return {'type': 'string', 'format': 'date-time'}
        elif isinstance(field, fields.ToOne):
            return self._get_ref(field.resource_class, field.embedded)
        elif isinstance(field, fields.ToMany):
            return {
                'type': 'array',
                'items': self._get_ref(field.resource_class, field.embedded)
            }
        elif isinstance(field, Reference):
            return self._get_ref(field.resource_class)

        else:
            try:
                field_type = {
                    fields.Boolean: 'boolean',
                    fields.Integer: 'integer',
                    fields.Number: 'number',
                    fields.String: 'string',
                    fields.Array: 'array',
                    fields.Arbitrary: 'object',
                    fields.KeyValue: 'object'
                }[field.__class__]
            except KeyError:
                field_type = 'string'

        return {'type': field_type}

    def _complete_url(self, uri):
        return self.api._complete_url(uri, '')

    def get_resource_definition(self, resource):
        definitions, properties = self.get_definitions(resource)

        resource_definition = {
            'type': 'object',
            'definitions': definitions,
            'properties': dict((name, ref) for name, ref in properties.items()),
            'links': sorted(self.get_links(resource), key=itemgetter('rel'))
        }

        if resource._required_fields:
            resource_definition['required'] = [field for field in resource._required_fields]

        return resource_definition

    def get_definitions(self, resource):
        definitions = {}
        properties = {}

        # noinspection PyProtectedMember
        for name, field in resource._fields.items():
            definition = field.schema

            if '$ref' in definition:
                properties[name] = definition
                continue

            if name in resource._read_only_fields:
                definition['readOnly'] = True

            definitions[name] = definition
            properties[name] = {'$ref': '#/definitions/{}/definitions/{}'.format(resource.endpoint, name)}

        definitions['_uri'] = {
            'type': 'string',
            'format': 'uri',
            'readOnly': True
        }
        properties['_uri'] = self._get_ref(resource, False)
        return definitions, properties

    def get_links(self, resource):
        paginated = issubclass(resource, ModelResource)

        yield {
            'rel': 'self',
            'href': self._complete_url('/{}/{{id}}'.format(resource.endpoint)),
            'method': 'GET',
        }

        instances = {
            'rel': 'instances',
            'href': self._complete_url('/{}'.format(resource.endpoint)),
            'method': 'GET'
        }

        if paginated:
            instances['schema'] = {
                '$ref': '#/definitions/_pagination'
            }

        yield instances

        # TODO POST etc. methods, accounting for required_fields

        for name, child in resource.nested_types.items():
            uri = '/{}/{}'.format(resource.endpoint, name) if child.collection else '/{}/{{id}}/{}'.format(resource.endpoint, name)
            link = {
                'rel': name,
                'href': self._complete_url(uri)
            }

            if isinstance(child, ResourceAction):
                properties = {}
                for arg in child._parser.args:

                    if child.method in ('POST', 'PATCH'):
                        if 'json' not in arg.location:
                            continue

                    properties[arg.name] = self._get_field_type(arg.type)

                    if arg.required:
                        properties['required'] = True

                link['method'] = child.method

                link.update({
                    'schema': {
                        'properties': properties
                    }
                })
            elif isinstance(child, Relationship):
                # TODO include HTTP methods (multiple methods possible, GET, POST, DELETE mainly)
                paginated = issubclass(resource, ModelResource)

                if paginated:
                    link.update({
                        'schema': {
                            '$ref': '#/definitions/_pagination'
                        }
                    })

                link.update({
                    'targetSchema': {
                        'type': 'array',
                        'items': {
                            '$ref': '#/definitions/{}'.format(child.resource.endpoint)
                        }
                    }
                })

            yield link

    def dispatch_request(self):
        return self.api.schema, 200