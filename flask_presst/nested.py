from functools import wraps
from flask import request
from flask.ext.restful import reqparse, abort, Resource
from flask.views import http_method_funcs
from werkzeug.utils import cached_property
from flask_presst.parsing import PresstArgument


class NestedProxy(object):
    relationship_name = None
    bound_resource = None
    collection = False

    def __init__(self, methods=('GET', )):
        self._methods = methods

    def __call__(self, instance, parent_id=None, *args, **kwargs):
        # FIXME Remove this (re-implement in ResourceMethod as regular callable)
        if request.method not in self._methods:
            abort(405)

        # fail if a collection type is called on an item and vice-versa:
        if self.collection != parent_id is None:
            abort(500)

        return self.dispatch_request(instance, parent_id, *args, **kwargs)

    def dispatch_request(self, *args, **kwargs):
        raise NotImplementedError()

    @classmethod
    def _with_object(cls, fn):
        @wraps(fn)
        def with_object(parent_id=None, *args, **kwargs):
            if cls.collection:
                return fn(*args, **kwargs)
            else:
                parent_item = cls.bound_resource.get_item_for_id(parent_id)
                return fn(parent_item, *args, **kwargs)
        return with_object


def resource_method(method='POST', collection=False):
    class _ResourceMethod(NestedProxy):
        def __init__(self, fn):
            super(_ResourceMethod, self).__init__(methods=(method, ))
            self._fn = fn
            self._parser = reqparse.RequestParser(argument_class=PresstArgument)

        def add_argument(self, name, location=('json', 'values'), **kwargs):
            self._parser.add_argument(name, location=location, **kwargs)

        def dispatch_request(self, instance, parent_id, *args, **kwargs):
            kwargs.update(self._parser.parse_args())

            if not self.collection:
                args = (self.bound_resource.get_item_for_id(parent_id),) + args

            return self._fn.__call__(instance, *args, **kwargs)

    _ResourceMethod.collection = collection
    return _ResourceMethod



class Relationship(NestedProxy):
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

    def __init__(self, resource, relationship_name=None, *args, **kwargs):
        super(Relationship, self).__init__(*args, **kwargs)
        self._resource = resource
        self.relationship_name = relationship_name

    @cached_property # FIXME won't actually cache unless at class level.
    def resource_class(self):
        return self.bound_resource.api.get_resource_class(self._resource, self.bound_resource.__module__)

    def dispatch_request(self, instance, *args, **kwargs):
        return getattr(self, request.method.lower())(*args, **kwargs)

    def get(self, parent_id):
        parent_item = self.bound_resource.get_item_for_id(parent_id)
        return self.resource_class.marshal_item_list(
            self.resource_class.get_item_list_for_relationship(self.relationship_name, parent_item))

    def patch(self, parent_id):
        abort(405) # Collections can't be PATCHED.

    def post(self, parent_id, item_id):
        """

        GET /A -> [{"resource_uri": '/A/1' .. }]
        GET /B/1/rel_to_a -> []
        POST /B/1/rel_to_b/1 -> {"resource_uri": '/A/1' ..}
        GET /B/1/rel_to_a -> [{"resource_uri": '/A/1' ..}]

        """
        parent_item = self.bound_resource.get_item_for_id(parent_id)
        return self.resource_class.marshal_item(
            self.resource_class.create_item_relationship(item_id, self.relationship_name, parent_item))

    def delete(self, parent_item):
        pass # TODO look up permissions in nested resource; only support deletion of links; deletion of actual model needs to be explicit.
