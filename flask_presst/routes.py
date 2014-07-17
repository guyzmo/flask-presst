from collections import OrderedDict
from functools import wraps
import itertools

from flask import request
from flask.views import View, MethodView
from werkzeug.utils import cached_property

from flask_presst.fields import Raw
from flask_presst.references import ResourceRef, ItemWrapper, ItemListWrapper, EmbeddedJob
from flask_presst.parse import SchemaParser


class ResourceRoute(object):
    """
    Specify custom views on a resource.
    """
    bound_resource = None

    def __init__(self, methods, collection=False, relationship_name=None):
        self.methods = methods
        self.collection = collection
        self.relationship_name = relationship_name

    @property
    def uri(self):
        if self.collection:
            return '{}/{}'.format(self.bound_resource.route_prefix, self.relationship_name)
        return '{}/{{id}}/{}'.format(self.bound_resource.route_prefix, self.relationship_name)

    def get_links(self):
        """
        Returns an iterable containing all the links for this route.
        """
        for method in self.methods:
            yield {
                'rel': '{}:{}'.format(self.relationship_name, method)
                        if len(self.methods) > 1 else self.relationship_name,
                'href': self.uri,
                'method': method
            }

    def view_factory(self, name, bound_resource):  # pragma: no cover
        """
        Returns a view function.

        :param name: name of the endpoint
        :param bound_resource: name of the resource to bind to
        """
        raise NotImplementedError()


class ResourceSchema(ResourceRoute, View):
    def __init__(self, **kwargs):
        self.bound_resource = kwargs.pop('bound_resource', None)
        super(ResourceSchema, self).__init__(['GET'], collection=True, **kwargs)

        # TODO bind resources only in the view_factory, not before.

    def view_factory(self, name, bound_resource):
        return self.as_view(name,
                            bound_resource=bound_resource,
                            relationship_name=self.relationship_name)

    def dispatch_request(self):
        resource = self.bound_resource
        schema = OrderedDict()

        for schema_property in ('title', 'description'):
            if schema_property in resource._meta:
                schema[schema_property] = resource._meta[schema_property]

        links = [
            {
                'rel': 'self',
                'href': resource.api._complete_url('{}/{{id}}'.format(resource.route_prefix), ''),
                'method': 'GET',
            },
            {
                'rel': 'instances',
                'href': resource.api._complete_url('{}'.format(resource.route_prefix), ''),
                'method': 'GET',
                'schema': {
                    '$ref': resource.api._complete_url('/schema#/definitions/_pagination', '')
                }
            }
        ]

        links = itertools.chain(links, *(route.get_links() for name, route in sorted(resource.routes.items())
                                         if name != 'schema'))

        schema['type'] = 'object'
        schema['definitions'] = definitions = {}
        schema['properties'] = properties = {}
        schema['required'] = resource._required_fields
        schema['links'] = list(links)

        # fields:
        for name, field in sorted(resource._fields.items()):
            definition = field.schema

            if '$ref' in definition:
                properties[name] = definition
                continue

            if name in resource._read_only_fields:
                definition['readOnly'] = True

            definitions[name] = definition
            properties[name] = {'$ref': '#/definitions/{}'.format(name)}

        definitions['_uri'] = {
            'type': 'string',
            'format': 'uri',
            'readOnly': True
        }

        properties['_uri'] = {
            '$ref': '#/definitions/_uri'
        }

        # TODO enforce Content-Type: application/schema+json (overwritten by Flask-RESTful)
        return schema


class ResourceAction(ResourceRoute):
    def __init__(self, fn, method, *args, **kwargs):
        super(ResourceAction, self).__init__([method], *args, **kwargs)
        self.method = method
        self._fn = fn
        self._parser = parser = SchemaParser({})

        annotations = getattr(fn, '__annotations__', {})
        self.target_schema = annotations.get('return', {})

        for name, field in annotations.items():
            if name != 'return':
                parser.add(field.attribute or name, field, required=True)


    def add_argument(self, name, field, **kwargs):
        """
        Adds an argument to the :class:`SchemaParser`. When a request to a :class:`ResourceAction` is
        made, the request is first parsed. If the parsing succeeds, the results are added as keyword arguments
        to the wrapped function.

        :param name: name of argument
        :param field: a Flask-Presst field
        :param bool required: whether the argument must exist
        """
        self._parser.add(name, field, **kwargs)

    @property
    def schema(self):
        return self._parser.schema

    @property
    def target_schema(self):
        if isinstance(self._target_schema, Raw):
            return self._target_schema.schema
        else:
            return self._target_schema or {}

    @target_schema.setter
    def target_schema(self, value):
        self._target_schema = value

    def get_links(self):
        yield {
            'rel': '{}'.format(self.relationship_name),
            'href': self.uri,
            'method': self.method,
            'schema': self.schema,
            'targetSchema': self.target_schema
        }

    def view_factory(self, name, bound_resource):
        def view(*args, **kwargs):
            # NOTE this may be inefficient with certain collection types that do not support lazy loading:
            if self.collection:
                item_or_items = bound_resource.get_item_list()
            else:
                parent_id = kwargs.pop('parent_id')
                item_or_items = bound_resource.get_item_for_id(parent_id)

            # noinspection PyCallingNonCallable
            kwargs.update(self._parser.parse_request())
            resource_instance = bound_resource()

            return self._fn.__call__(resource_instance, item_or_items, *args, **EmbeddedJob.complete(kwargs))

            # TODO automatic commit here
        return view

    def __get__(self, obj, *args, **kwargs):
        if obj is None:
            return self
        return lambda *args, **kwargs: self._fn.__call__(obj, *args, **kwargs)


def action(method='POST', collection=False):
    """
    A decorator for attaching custom routes to a :class:`PresstResource`.

    Depending on whether ``collection`` is ``True``, the route is either ``/resource/action``
    or ``/resource/{id}/action`` and the decorator passes either the list of items from
    :meth:`PresstResource.get_item_list` or the single item.

    :param str method: one of 'POST', 'GET', 'PATCH', 'DELETE'
    :param bool collection: whether this is a collection method or item method
    :returns: :class:`ResourceAction` instance
    """
    def wrapper(fn):
        return wraps(fn)(ResourceAction(fn, method, collection))
    return wrapper


class Relationship(ResourceRoute, MethodView):
    """
    :class:`Relationship` views, when attached to a :class:`PresstResource`, create a route that maps from
    an item in one resource to a collection of items in another resource.

    :class:`Relationship` makes use of SqlAlchemy's `relationship` attributes. To support pagination on these objects,
    the relationship must return a query object. Therefore, the :func:`sqlalchemy.orm.relationship` must have the
    attribute :attr:`lazy` set to ``'dynamic'``. The same goes for any :func:`backref()`.

    :param resource: target resource name
    :param str backref: hint needed when there is a required `ToOne` field referencing back from the target resource
    :param str relationship_name: alternate attribute name in resource item
    """

    def __init__(self, resource,
                 relationship_name=None,
                 backref=None, **kwargs):
        super(Relationship, self).__init__(kwargs.pop('methods', ['GET', 'POST', 'DELETE']))
        self.reference_str = resource
        self.relationship_name = relationship_name
        self.bound_resource = kwargs.pop('bound_resource', None)
        self.backref = backref

    @cached_property
    def resource(self):
        return ResourceRef(self.reference_str).resolve()

    def get_links(self):
        return [
            {
                'rel': self.relationship_name,
                'href': self.uri,
                'method': 'GET',
                'schema': {
                    '$ref': self.bound_resource.api._complete_url('/schema#/definitions/_pagination', '')
                },
                'targetSchema': {
                    'type': 'array',
                    'items': {
                        '$ref': self.bound_resource.api._complete_url('{}/schema#'.format(self.resource.route_prefix), '')
                    }
                }
            },
            {
                'rel': '{}:create'.format(self.relationship_name),
                'href': self.uri,
                'method': 'POST',
                'schema': {
                    'oneOf': [
                        {'$ref': '{}/schema#/definitions/_uri'.format(self.resource.route_prefix)},
                        {'$ref': '{}/schema#'.format(self.resource.route_prefix)},
                        {
                            'type': 'array',
                            'items': {
                                'oneOf': [
                                    {'$ref': '{}/schema#/definitions/_uri'.format(self.resource.route_prefix)},
                                    {'$ref': '{}/schema#'.format(self.resource.route_prefix)},
                                ]
                            }
                        }
                    ]
                }
            },
            {
                'rel': '{}:delete'.format(self.relationship_name),
                'href': self.uri,
                'method': 'DELETE',
                'schema': {
                    'oneOf': [
                        {'$ref': '{}/schema#/definitions/_uri'.format(self.resource.route_prefix)},
                        {
                            'type': 'array',
                            'items': {
                                '$ref': '{}/schema#/definitions/_uri'.format(self.resource.route_prefix)
                            }
                        }
                    ]
                }
            }
        ]

    def view_factory(self, name, bound_resource):
        return self.as_view(name,
                            bound_resource=bound_resource,
                            resource=self.reference_str,
                            relationship_name=self.relationship_name,
                            backref=self.backref,
                            methods=self.methods)

    def get(self, parent_id):
        parent = ItemWrapper.read(self.bound_resource, parent_id)
        return parent.get_relationship(self.relationship_name, target_resource=self.resource).marshal()

    def post(self, parent_id):
        #parent_item = self.bound_resource.get_item_for_id(parent_id)
        parent = ItemWrapper.read(self.bound_resource, parent_id)

        if self.backref:
            resolve = {self.backref: parent.raw()}
        else:
            resolve = None

        item_or_items = ItemListWrapper.resolve(self.resource,
                                                request.json,
                                                resolved_properties=resolve,
                                                create=True,
                                                update=True,
                                                commit=False)

        return parent.add_to_relationship(self.relationship_name, item_or_items, commit=True).marshal()

    def delete(self, parent_id):
        parent = ItemWrapper.read(self.bound_resource, parent_id)
        item_or_items = ItemListWrapper.resolve(self.resource, request.json, create=False, update=False)
        parent.remove_from_relationship(self.relationship_name, item_or_items, commit=True)
        return None, 204