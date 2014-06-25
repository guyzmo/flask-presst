from functools import wraps
from flask import request
from flask_restful import reqparse, abort, Resource
from flask.views import http_method_funcs, View, MethodView
import six
from werkzeug.utils import cached_property
from flask_presst.parsing import PresstArgument


class NestedProxy(object):
    bound_resource = None

    def __init__(self, methods, collection=False, relationship_name=None):
        self.methods = methods
        self.collection = collection
        self.relationship_name = relationship_name

    def view_factory(self, name, bound_resource):  # pragma: no cover
        raise NotImplementedError()


class ResourceMethod(NestedProxy):
    def __init__(self, fn, method, *args, **kwargs):
        super(ResourceMethod, self).__init__([method], *args, **kwargs)
        self.method = method
        self._fn = fn
        self._parser = reqparse.RequestParser(argument_class=PresstArgument)

    def add_argument(self, name, location=('json', 'values'), **kwargs):
        """
        Adds an argument to the :class:`reqparse.RequestParser`. When a request to a :class:`ResourceMethod` is
        made, the request is first parsed. If the parsing succeeds, the results are added as keyword arguments
        to the wrapped function.

        :param name: name of argument
        :param location: attribute of the request object to search; e.g `json` or `args`.
        :param bool required: whether the argument must exist
        :param default: default value
        :param type: a callable, or a Flask-Presst or Flask-RESTful field
        """
        self._parser.add_argument(name, location=location, **kwargs)

    def view_factory(self, name, bound_resource):
        def view(*args, **kwargs):

            # NOTE this may be inefficient with certain collection types that do not support lazy loading:
            if self.collection:
                item_or_items = bound_resource.get_item_list()
            else:
                parent_id = kwargs.pop('parent_id')
                item_or_items = bound_resource.get_item_for_id(parent_id)

            # noinspection PyCallingNonCallable
            kwargs.update(self._parser.parse_args())
            resource_instance = bound_resource()

            return self._fn.__call__(resource_instance, item_or_items, *args, **kwargs)

        return view

    def __get__(self, obj, *args, **kwargs):
        if obj is None:
            return self
        return lambda *args, **kwargs: self._fn.__call__(obj, *args, **kwargs)


def resource_method(method='POST', collection=False):
    """
    A decorator for attaching custom routes to a :class:`PresstResource`.

    Depending on whether ``collection`` is ``True``, the route is either ``/resource/method``
    or ``/resource/{id}/method`` and the decorator passes either the list of items from
    :meth:`PresstResource.get_item_list` or the single item.

    :param str method: one of 'POST', 'GET', 'PATCH', 'DELETE'
    :param bool collection: whether this is a collection method or item method
    :returns: :class:`ResourceMethod` instance
    """
    def wrapper(fn):
        return wraps(fn)(ResourceMethod(fn, method, collection))
    return wrapper


class Relationship(NestedProxy, MethodView):
    """
    :class:`Relationship` views, when attached to a :class:`PresstResource`, create a route that maps from
    an item in one resource to a collection of items in another resource.

    :class:`Relationship` makes use of SqlAlchemy's `relationship` attributes. To support pagination on these objects,
    the relationship must return a query object. Therefore, the :func:`sqlalchemy.orm.relationship` must have the
    attribute :attr:`lazy` set to ``'dynamic'``. The same goes for any :func:`backref()`.

    :param resource: resource class, resource name, or SQLAlchemy model
    :param str relationship_name: alternate attribute name in resource item
    """

    def __init__(self, resource,
                 relationship_name=None, **kwargs):
        super(Relationship, self).__init__(kwargs.pop('methods', ['GET', 'POST', 'DELETE']))
        self.resource = resource
        self.relationship_name = relationship_name
        self.bound_resource = kwargs.pop('bound_resource', None)

    @cached_property
    def resource_class(self):
        return self.bound_resource.api.get_resource_class(self.resource, self.bound_resource.__module__)

    def view_factory(self, name, bound_resource):
        return self.as_view(name,
                            bound_resource=bound_resource,
                            resource=self.resource,
                            relationship_name=self.relationship_name,
                            methods=self.methods)

    def _resolve_item_id_from_request_data(self):
        if not isinstance(request.json, six.string_types):
            abort(400, message='Need resource URI in body of JSON request.')

        resource_class, item_id = self.resource_class.api.parse_resource_uri(request.json)

        if self.resource_class != resource_class:
            abort(400, message='Wrong resource item type, expected {0}, got {1}'.format(
                self.resource_class.resource_name,
                self.resource_class.resource_name
            ))

        return item_id

    def get(self, parent_id):
        parent_item = self.bound_resource.get_item_for_id(parent_id)
        return self.resource_class.marshal_item_list(
            self.resource_class.get_item_list_for_relationship(self.relationship_name, parent_item))

    def post(self, parent_id, item_id=None):
        parent_item = self.bound_resource.get_item_for_id(parent_id)

        if not item_id:  # NOTE not implemented: POST /parent/A/child/B; instead get item from request.data
            item_id = self._resolve_item_id_from_request_data()

        return self.resource_class.marshal_item(
            self.resource_class.create_item_relationship(item_id, self.relationship_name, parent_item))

    def delete(self, parent_id, item_id=None):
        parent_item = self.bound_resource.get_item_for_id(parent_id)

        if not item_id:  # NOTE not implemented: DELETE /parent/A/child/B;, instead get item from request.data
            item_id = self._resolve_item_id_from_request_data()

        self.resource_class.delete_item_relationship(item_id, self.relationship_name, parent_item)
        return None, 204