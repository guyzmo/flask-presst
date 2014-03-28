from functools import wraps
from flask import request
from flask.ext.restful import reqparse, abort, Resource
from flask.views import http_method_funcs, View, MethodView
import six
from werkzeug.utils import cached_property
from flask.ext.presst.utils.routes import route_from
from flask_presst.parsing import PresstArgument


class NestedProxy(object):
    bound_resource = None

    def __init__(self, methods, collection=False, relationship_name=None):
        self.methods = methods
        self.collection = collection
        self.relationship_name = relationship_name

    def view_factory(self, name, bound_resource):  # pragma: no cover
        raise NotImplementedError()


class _ResourceMethod(NestedProxy):
    def __init__(self, fn, *args, **kwargs):
        super(_ResourceMethod, self).__init__(*args, **kwargs)
        self._fn = fn
        self._parser = reqparse.RequestParser(argument_class=PresstArgument)

    def add_argument(self, name, location=('json', 'values'), **kwargs):
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
    def wrapper(fn):
        if isinstance(method, (list, tuple)):
            methods = method
        else:
            methods = [method]

        return wraps(fn)(_ResourceMethod(fn, methods, collection))
    return wrapper


class Relationship(NestedProxy, MethodView):
    """
    Resource Methods:

    A :class:`_RelationshipResource` inherits all resource methods that apply to the collection.
    This means that `/resource_a/1/resource_b/method` works, but `/resource_a/1/resource_b/1/method`
    does not, since `/resource_a/1/resource_b/1/method` would be identical to `/resource_b/1/method`
    and therefore redundant.

    Also, while collection methods on nested resources are supported, deep nesting such as
    `/resource_a/1/resource_b/resource_c/` is not. The proper way to resolve deeply nested resources is to first call.
    `/resource_a/1/resource_b` and then request `/resource_b/*/resource_c` for every item that has been returned.

    By the same measure, `/resource_a/1/resource_b/1/resource_c/` is not supported, and that statement would in any
    case be identical to `/resource_b/1/resource_c/`.

    While  shallow nesting may necessitate multiple API calls in edge situations and seem less efficient, shallow
    nesting has the advantage of avoiding a proliferation of resource endpoints and of having to deal with circular
    dependencies.

    .. note:: A special case, if implemented, will be *child resources*, where an item in a certain resource can only be
        accessed through its parent resource. But these will not be defined using :class:`_RelationshipResource`.

    :class:`_RelationshipResource` makes use of SqlAlchemy's `relationship` attributes. For :class:`_RelationshipResource` to
    support pagination on these objects, the relationship must return a query object. This is achieved by setting the
    relationship parameter :attr:`lazy` to `'dynamic'`, which has to be done both on the forward relationship as well
    as any :func:`backref()`.
    """

    def __init__(self, resource,
                 relationship_name=None,
                 methods=None,
                 bound_resource=None, *args, **kwargs):
        super(Relationship, self).__init__(methods or ['GET', 'POST', 'DELETE'])
        self.resource = resource
        self.relationship_name = relationship_name
        self.bound_resource = bound_resource

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