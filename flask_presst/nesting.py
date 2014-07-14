from functools import wraps
from flask import request
from flask_restful import reqparse, abort, Resource
from flask.views import http_method_funcs, View, MethodView
import six
from werkzeug.utils import cached_property
from flask.ext.presst.references import ResourceRef
from flask_presst.parse import PresstArgument


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

    def view_factory(self, name, bound_resource):
        return self.as_view(name,
                            bound_resource=bound_resource,
                            resource=self.reference_str,
                            relationship_name=self.relationship_name,
                            backref=self.backref,
                            methods=self.methods)

    def _get_or_create_item(self, data, resolve=None):
        if isinstance(data, six.text_type):
            return self.resource.get_item_from_uri(data)
        elif isinstance(data, dict) and 'resource_uri' in data:
            return self.resource.get_item_from_uri(data.pop('resource_uri'), changes=data)
        else:
            return self.resource.request_make_item(data=data, resolve=resolve)

    def _get_item(self, data):
        if isinstance(data, six.text_type):
            return self.resource.get_item_from_uri(data)
        elif isinstance(data, dict) and 'resource_uri' in data:
            return self.resource.get_item_from_uri(data.pop('resource_uri'))
        else:
            abort(400, message='Resource URI missing in JSON dictionary')

    @staticmethod
    def _request_parse_items(fn, *args, **kwargs):
        data = request.json

        if data is None:
            abort(400, message='JSON required')

        if not isinstance(data, (dict, list, six.text_type)):
            abort(400, message='JSON dictionary, string, or array required')

        if isinstance(data, list):
            return [fn(d, *args, **kwargs) for d in data], True
        else:
            return fn(data, *args, **kwargs), False

    def get(self, parent_id):
        parent_item = self.bound_resource.get_item_for_id(parent_id)
        return self.resource.marshal_item_list(
            self.bound_resource.get_relationship(parent_item, self.relationship_name))

    def post(self, parent_id):
        parent_item = self.bound_resource.get_item_for_id(parent_id)

        if self.backref:
            resolve = {self.backref: parent_item}
        else:
            resolve = None

        item_or_items, is_list = self._request_parse_items(self._get_or_create_item, resolve=resolve)

        self.bound_resource.begin()

        if is_list:
            result = [self.bound_resource.add_to_relationship(parent_item, self.relationship_name, item)
                      for item in item_or_items]

            self.bound_resource.commit()

            return self.resource.marshal_item_list(result)
        else:
            result = self.bound_resource.add_to_relationship(parent_item, self.relationship_name, item_or_items)

            self.bound_resource.commit()

            return self.resource.marshal_item(result)

    def delete(self, parent_id):
        parent_item = self.bound_resource.get_item_for_id(parent_id)
        item_or_items, is_list = self._request_parse_items(self._get_item)

        self.bound_resource.begin()

        if is_list:
            for item in item_or_items:
                self.bound_resource.remove_from_relationship(parent_item, self.relationship_name, item)
        else:
            self.bound_resource.remove_from_relationship(parent_item, self.relationship_name, item_or_items)

        self.bound_resource.commit()
        return None, 204