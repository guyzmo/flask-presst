from collections import OrderedDict
from functools import wraps
import itertools
import re

from flask import request, url_for
from flask_restful import marshal, unpack
from flask.views import View, MethodView
from werkzeug.utils import cached_property

from flask_presst.fields import Raw
from flask_presst.references import ResourceRef, ItemWrapper, ItemListWrapper, EmbeddedJob
from flask_presst.parse import SchemaParser


def url_rule_to_uri_pattern(rule):
    # TODO convert from underscore to camelCase
    return re.sub(r'<(\w+:)?([^>]+)>', r'{\2}', rule)


class ResourceRoute(object):
    def __init__(self, binding=None, attribute=None):
        self.binding = binding
        self.attribute = attribute

    def get_url_rule(self, binding=None):
        raise NotImplementedError()

    def get_links(self, binding=None):
        raise NotImplementedError()

    def view_factory(self, name, binding):  # pragma: no cover
        """
        Returns a view function.

        :param name: name of the endpoint
        :param binding: class of the resource to bind to
        """
        raise NotImplementedError()


class SchemaView(object):
    def __init__(self, fn, properties=None, response_property=None):
        annotations = getattr(fn, '__annotations__', {})
        self._response_property = annotations.get('return', response_property)
        self._schema_parser = schema = SchemaParser(properties or {})
        self._fn = fn

        for name, field in annotations.items():
            if name != 'return':
                schema.add(field.attribute or name, field, required=True)

    @property
    def schema(self):
        return self._schema_parser.schema

    @property
    def target_schema(self):
        if self._response_property is None:
            return None
        return self._response_property.schema

    def _marshal_response(self, response):
        if self.target_schema is None:
            return response
        elif isinstance(response, tuple):
            data, code, headers = unpack(response)

            if isinstance(self._response_property, Raw):
                return self._response_property.format(data), code, headers
            else:
                return marshal(data, self._response_property), code, headers
        else:
            if isinstance(self._response_property, Raw):
                return self._response_property.format(response)
            else:
                return marshal(response, self._response_property)

    def add_argument(self, name, field, **kwargs):
        """
        Add an argument to view function.

        :param name: name of argument
        :param field: a Flask-Presst field for parsing
        :param bool required: whether the argument must exist
        """
        self._schema_parser.add(name, field, **kwargs)

    def dispatch_request(self, instance, *args, **kwargs):
        kwargs.update(self._schema_parser.parse_request())
        response = self._fn(instance, *args, **EmbeddedJob.complete(kwargs))
        return self._marshal_response(response)


class ItemView(SchemaView):
    def dispatch_request(self, instance, *args, **kwargs):
        print(instance, args, kwargs)
        item = instance.get_item_for_id(kwargs.pop('id'))
        return super(ItemView, self).dispatch_request(instance, item, *args, **kwargs)


class CollectionView(SchemaView):
    def dispatch_request(self, instance, *args, **kwargs):
        items = instance.get_item_list()
        return super(CollectionView, self).dispatch_request(instance, items, *args, **kwargs)


class ResourceMultiRoute(ResourceRoute):
    """

    :param route: if the route is not set, the attribute name within the resource it belongs to will be used
    """

    def __init__(self,
                 method_func,
                 method='GET',
                 route=None,
                 attribute=None,
                 binding=None,
                 view_class=SchemaView,
                 view_methods=None,
                 **view_kwargs):

        super(ResourceMultiRoute, self).__init__(binding, attribute)
        self.route = route

        self._view_class = view_class
        self._view_methods = view_methods = view_methods.copy() if view_methods else {}
        self._current_view = view = view_class(method_func, **view_kwargs)
        view_methods[method] = view

        # self._schema_parser = SchemaParser(properties or {})
        # self._response_schema = response_schema
        # self._marshal_response = marshal_response and response_schema is not None

    def __getattr__(self, name):
        return getattr(self._current_view, name)

    def __get__(self, obj, *args, **kwargs):
        if obj is None:
            return self
        return lambda *args, **kwargs: self._current_view._fn.__call__(obj, *args, **kwargs)

    def _add_method(self, method, fn):
        return type(self)(method_func=fn,
                          method=method,
                          attribute=self.attribute,
                          route=self.route,
                          view_class=self._view_class,
                          view_methods=self._view_methods)

    def GET(self, fn):
        return self._add_method('GET', fn)

    def PUT(self, fn):
        return self._add_method('PUT', fn)

    def POST(self, fn):
        return self._add_method('POST', fn)

    def PATCH(self, fn):
        return self._add_method('PATCH', fn)

    def DELETE(self, fn):
        return self._add_method('DELETE', fn)

    @property
    def methods(self):
        return list(self._view_methods.keys())

    def get_url_rule(self, binding=None):
        if self.route:
            return self.route
        else:
            return '/{}'.format(self.attribute)

    def get_links(self, binding=None):
        """
        :returns: an iterable containing all the links for this route.
        """
        single_method = len(self._view_methods) == 1

        for method, meth in self._view_methods.items():
            if single_method:
                rel = self.attribute
            else:
                rel = '{}:{}'.format(self.attribute, method.lower())

            yield {
                'rel': rel,
                'href': '{}{}'.format(url_for(binding.endpoint), url_rule_to_uri_pattern(self.get_url_rule(binding))),
                'method': method,
                'schema': meth.schema,
                'targetSchema': meth.target_schema or {}
            }

    def view_factory(self, name, binding):
        def view(*args, **kwargs):
            view = self._view_methods[request.method.upper()]
            resource_instance = binding()
            return view.dispatch_request(resource_instance, *args, **kwargs)

        return view


class ResourceItemMultiRoute(ResourceMultiRoute):
    def get_url_rule(self, binding):
        pk_converter = binding._meta.get('pk_converter', 'int')

        if self.route:
            route = self.route
        else:
            route = '/{}'.format(self.attribute)

        return '/<{}:id>{}'.format(pk_converter, route)


def route(method='GET', route=None, **view_kwargs):
    """
    Decorator generating a :class:`ResourceMultiRoute`. Creates an endpoint for one or more methods.

    .. attribute:: GET

        Decorator --- shortcut for ``route('GET')``. Can be called with and without additional arguments.

    .. attribute:: PUT

        Decorator --- shortcut for ``route('PUT')``. Can be called with and without additional arguments.

    .. attribute:: POST

        Decorator --- shortcut for ``route('POST')``. Can be called with and without additional arguments.

    .. attribute:: PATCH

        Decorator --- shortcut for ``route('PATCH')``. Can be called with and without additional arguments.

    .. attribute:: DELETE

        Decorator --- shortcut for ``route('DELETE')``. Can be called with and without additional arguments.

    :param str method:
    :param str route:
    :param str attribute:
    :param dict properties:
    :param Raw response_property:
    """

    def wrapper(fn):
        return wraps(fn)(ResourceMultiRoute(fn,
                                            method,
                                            route=route,
                                            **view_kwargs))

    return wrapper


for method in ('GET', 'PUT', 'POST', 'PATCH', 'DELETE'):
    def factory(method):
        def method_wrapper(fn=None, **kwargs):
            if fn and callable(fn):
                return ResourceMultiRoute(fn, method=method)
            else:
                return route(method=method, **kwargs)

        return method_wrapper

    setattr(route, method, factory(method))


def action(method='POST', collection=False, **kwargs):
    """
    A decorator for attaching custom routes to a :class:`Resource`.

    Depending on whether ``collection`` is ``True``, the route is either ``/resource/action``
    or ``/resource/{id}/action`` and the decorator passes either the list of items from
    :meth:`Resource.get_item_list` or the single item.

    :param str method: one of 'POST', 'GET', 'PATCH', 'DELETE'
    :param bool collection: whether this is a collection method or item method
    :param dict properties: initial dict of fields to feed the parser
    :param Raw response_property: optional field to use as targetSchema and for marshalling the result
    :returns: :class:`ResourceMultiRoute` or :class:`ResourceItemMultiRoute` instance
    """
    def wrapper(fn):
        if collection:
            return wraps(fn)(ResourceMultiRoute(fn, method, route=None, view_class=CollectionView, **kwargs))
        else:
            return wraps(fn)(ResourceItemMultiRoute(fn, method, view_class=ItemView, **kwargs))

    return wrapper


class Relationship(ResourceRoute, MethodView):
    """
    :class:`Relationship` views, when attached to a :class:`Resource`, create a route that maps from
    an item in one resource to a collection of items in another resource.

    :class:`Relationship` makes use of SqlAlchemy's `relationship` attributes. To support pagination on these objects,
    the relationship must return a query object. Therefore, the :func:`sqlalchemy.orm.relationship` must have the
    attribute :attr:`lazy` set to ``'dynamic'``. The same goes for any :func:`backref()`.

    :param resource: target resource name
    :param str backref: hint needed when there is a required `ToOne` field referencing back from the target resource
    :param str attribute: alternate attribute name in resource item
    """

    def __init__(self, resource, backref=None, attribute=None, **kwargs):
        super(Relationship, self).__init__(kwargs.pop('binding', None), attribute)
        self.reference_str = resource
        self.backref = backref

    @cached_property
    def resource(self):
        return ResourceRef(self.reference_str).resolve()

    def get_url_rule(self, binding=None):
        pk_converter = binding._meta.get('pk_converter', 'int')
        return '/<{}:id>/{}'.format(pk_converter, self.attribute)

    def get_links(self, binding):
        uri = '{}/{{id}}/{}'.format(url_for(binding.endpoint), self.attribute)

        return [
            {
                'rel': self.attribute,
                'href': uri,
                'method': 'GET',
                'schema': {
                    '$ref': self.binding.api._complete_url('/schema#/definitions/_pagination', '')
                },
                'targetSchema': {
                    'type': 'array',
                    'items': {
                        '$ref': self.binding.api._complete_url('{}/schema#'.format(self.resource.route_prefix), '')
                    }
                }
            },
            {
                'rel': '{}:create'.format(self.attribute),
                'href': uri,
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
                'rel': '{}:delete'.format(self.attribute),
                'href': uri,
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

    def view_factory(self, name, binding):
        return self.as_view(name,
                            binding=binding,
                            resource=self.reference_str,
                            attribute=self.attribute,
                            backref=self.backref,
                            methods=self.methods)

    def get(self, id):
        parent = ItemWrapper.read(self.binding, id)
        return parent.get_relationship(self.attribute, target_resource=self.resource).marshal()

    def post(self, id):
        #parent_item = self.binding.get_item_for_id(parent_id)
        parent = ItemWrapper.read(self.binding, id)

        if self.backref:
            resolve = {self.backref: parent.raw()}
        else:
            resolve = None

        item_or_items = ItemListWrapper.resolve(self.resource,
                                                request.json,
                                                resolved_properties=resolve,
                                                create=True,
                                                update=False,  # NOTE not supported for sanity reasons
                                                commit=False)

        return parent.add_to_relationship(self.attribute, item_or_items, commit=True).marshal()

    def delete(self, id):
        parent = ItemWrapper.read(self.binding, id)
        item_or_items = ItemListWrapper.resolve(self.resource, request.json, create=False, update=False)
        parent.remove_from_relationship(self.attribute, item_or_items, commit=True)
        return None, 204