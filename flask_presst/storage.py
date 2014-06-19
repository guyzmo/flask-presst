from collections import namedtuple
from functools import wraps
from urllib import request
from flask import current_app, url_for
import flask.ext.restful
from flask.ext.restful import abort
from flask.ext.restful.reqparse import RequestParser
from flask.ext.sqlalchemy import get_state
from flask.views import MethodViewType, MethodView, View
import six
from sqlalchemy.orm import object_session
from sqlalchemy.orm.exc import NoResultFound
from flask.ext.presst import PresstArgument
from flask.ext.presst.fields import RelationshipField
from flask.ext.presst.utils import pop

Up = namedtuple('Up', ['resource', 'relationship_name', 'id'])


class Store(object):
    """


    """

    def __init__(self, resource):
        self.resource = resource
        self.meta = resource._meta

    def get_item(self, id_, stack=None):
        raise NotImplementedError()

    def get_item_list(self, stack=None, pagination=None):
        raise NotImplementedError()

    def add_item_to_relationship(self, item, stack):
        raise NotImplementedError()

    def remove_items_from_relationship(self, item, stack):
        raise NotImplementedError()

    def create_item(self, args, stack=None):
        raise NotImplementedError()

    def update_item(self, id_, changes, patch=False, stack=None):
        raise NotImplementedError()

    def delete_item(self, id_, stack=None):
        raise NotImplementedError()


class SQLAlchemyStore(Store):

    def __init__(self, resource):
        super(SQLAlchemyStore, self).__init__(resource)
        self.model = self.meta.get('model', None)
        self.model_pk_column = self.meta.get('pk_column')

    @classmethod
    def _get_session(cls):
        return get_state(current_app).db.session

    def _get_raw_query(self, stack=None):
        if not stack:
            return self.model.query
        else:
            up, stack = pop(stack)
            # TODO better implementation for up-resources with SQLAlchemyStore that creates an appropriate query join
            parent_item = up.resource.store.get_item(up.id, stack=stack)

            query = getattr(parent_item, up.relationship_name)

            if isinstance(query, list):
                # SQLAlchemy relationships currently need join='dynamic' so that a query object is returned on the join
                abort(500, message='Unable to access {} from {}'.format(up.resource.resource_name, self.resource.resource_name))

            return query

    def get_item(self, id_, stack=None):
        try:  # SQLAlchemy's .get() does not work well with .filter()
            return self._get_raw_query(stack).filter(self.model_pk_column == id_).one()
        except NoResultFound:
            abort(404)

    def get_item_list(self, stack=None, pagination=None):
        query = self._get_raw_query(stack)

        # if paginate:
        #     return query

        # TODO pre-processors


        if pagination:
            raise NotImplementedError()

        return query.all()

    def add_item_to_relationship(self, item, stack):
        up, stack = pop(stack)
        parent_item = up.resource.store.get_item(up.id, stack=stack)
        session = object_session(parent_item)

        try:
            getattr(parent_item, up.relationship_name).append(item)
            session.commit()
        except:
            session.rollback()
            raise

    def remove_item_from_relationship(self, item, stack):
        up, stack = pop(stack)
        parent_item = up.resource.store.get_item(up.id, stack=stack)
        session = object_session(parent_item)

        try:
            getattr(parent_item, up.relationship_name).remove(item)
            session.commit()
        except:
            session.rollback()
            raise

    def create_item(self, args, stack=None):
        item = self.model()  # FIXME do this without calling actual init (__new__ isn't an option)

        for key, value in six.iteritems(args):
            setattr(item, key, value)

        if stack:
            self.add_item_to_relationship(item, stack)
        else:
            session = self._get_session()

            try:
                session.add(item)
                session.commit()
            except:
                session.rollback()
                raise  # TODO add proper error handling and abort() with message

    def update_item(self, id_, changes, patch=False, stack=None):
        item = self.get_item(id_, stack)
        session = object_session(item)

        try:
            for key, value in six.iteritems(changes):
                setattr(item, key, value)

            session.commit()
        except:
            session.rollback()
            raise  # TODO add proper error handling and abort() with message

        return item

    def delete_item(self, id_, stack=None):
        item = self.get_item(id_, stack)
        session = object_session(item)
        session.delete(item)
        session.commit()


class MemoryStore(Store):
    """
    :class:`MemoryStore` is a very simple :class:`Store` implementation that is primarily intended for testing.
    """

    def __init__(self, resource):
        super(MemoryStore, self).__init__(resource)
        self.items = resource.items or []
        self.id_field = self.meta.get('id_field', None)

    def _get_stack_items(self, stack):
        if stack:
            up, stack = pop(stack)
            parent_item = up.resource.get_item(up.id, stack=stack)
            return getattr(parent_item, up.relationship_name)
        else:
            return self.items

    def _item_get_id(self, item):
        return item[self.id_field]

    def _item_set_id(self, item, id_):
        item[self.id_field] = id_
        return item

    def _find_free_id(self, stack=None):
        items = self._get_stack_items(stack)
        return max(self._item_get_id(item) for item in items) + 1

    def get_item(self, id_, stack=None):
        items = self._get_stack_items(stack)

        for item in items:
            if self._item_get_id(item) == id_:
                return item
        abort(404)

    def get_item_list(self, stack=None, pagination=None):
        items = self._get_stack_items(stack)

        if pagination:
            raise NotImplementedError()

        return items

    def add_item_to_relationship(self, item, stack):
        up, stack = pop(stack)
        parent_item = up.resource.get_item(up.id, stack=stack)

        if hasattr(parent_item, up.relationship_name):
            relationship = getattr(parent_item, up.relationship_name)
            relationship.append(item)
        else:
            setattr(parent_item, up.relationship_name, [item])

    def remove_item_from_relationship(self, item, stack):
        up, stack = pop(stack)
        parent_item = up.resource.get_item(up.id, stack=stack)

        if not hasattr(parent_item, up.relationship_name):
            abort(404)
        else:
            relationship = getattr(parent_item, up.relationship_name)
            relationship.remove(item)

    def create_item(self, args, stack=None):
        item = self._item_set_id(args, self._find_free_id(stack))
        items = self._get_stack_items(stack)
        items.append(item)
        return item

    def update_item(self, id_, changes, patch=False, stack=None):
        item = self.get_item(id_, stack)
        item.update(changes)
        return item

    def delete_item(self, id_, stack=None):
        items = self._get_stack_items(stack)  # FIXME make stacks tuples.
        items.remove(self.get_item(id_, stack))




class ItemSchema(object):
    fields = None
    id_field = None
    id_converter = None
    read_only_fields = None
    required_fields = None

    def __init__(self,
                 fields,
                 required_fields=None,
                 read_only_fields=None,
                 embeddables=None,
                 id_field=None,
                 id_converter=None):
        """

        :param dict fields:
        :param dict embeddables: key-value mappings for any relationships or nested resources that may be embedded
            in the document when creating or updating an item.
        """
        self.fields = fields

        self.read_only_fields = required_fields or tuple()
        self.read_only_fields = read_only_fields or tuple()

        self.embeddables = embeddables or {}

        self.id_field = id_field or current_app.config.get('PRESST_DEFAULT_ID_FIELD', 'id')
        self.id_converter = id_converter or current_app.config.get('PRESST_DEFAULT_ID_CONVERTER', 'int')

    def parse_request(self, patch=False, reqparse=None):
        #
        # if patch:
        #     name for name in self._fields if name in request.json
        #
        parser = reqparse.RequestParser(argument_class=PresstArgument)

        if patch:
            fields = (name for name in self._fields if name in request.json)
        else:
            fields = self.fields

        for name in fields:
            if name not in self.read_only_fields:
                required = name in self.required_fields
                parser.add_argument(name, type=self.fields[name], required=required, ignore=not required)

        # TODO parse embeddable fields.

        return parser.parse_args()


class Leaf(View):

    def __init__(self, methods, collection=False, relationship_name=None, **kwargs):
        self.methods = methods
        self.collection = collection
        self.relationship_name = relationship_name
        self.up_resource = kwargs.pop('up_resource', None)
        self.stack_ids = kwargs.pop('stack_ids', ())

    def get_api_routes(self):
        if self.collection:
            up_route, up_ids, _ = self.up_resource.get_api_routes()['instances']
        else:
            up_route, up_ids, _ = self.up_resource.get_api_routes()['self']

        return {
            self.relationship_name: ('{}/{}'.format(up_route, self.relationship_name), up_ids, self.methods)
        }

    def make_stack(self, **kwargs):


        pass

    def view_factory(self, endpoint, stack_ids, *class_args, **class_kwargs):  # pragma: no cover
        return self.as_view(endpoint,
                            methods=self.methods,
                            collection=self.collection,
                            up_resource=self.up_resource,
                            relationship_name=self.relationship_name)


class Action(Leaf, View):
    # TODO support multiple methods, similar to property decorator.

    def __init__(self, fn, method, *args, **kwargs):
        super(Action, self).__init__([method], *args, **kwargs)
        self._fn = fn
        self._parser = RequestParser(argument_class=PresstArgument)

    def view_factory(self, endpoint, *class_args, **class_kwargs):  # pragma: no cover
        return self.as_view(endpoint,
                            methods=self.methods,
                            collection=self.collection,
                            up_resource=self.up_resource,
                            relationship_name=self.relationship_name)

    def dispatch_request(self, *args, stack, **kwargs):
            # NOTE this may be inefficient with certain collection types that do not support lazy loading:

            # BUILD STACK



            if self.collection:
                item_or_items = self.up_resource.storage.get_item_list(stack)
            else:
                parent_id = kwargs.pop('parent_id')
                # TODO id
                item_or_items = self.up_resource.storage.get_item(stack)

            # noinspection PyCallingNonCallable
            kwargs.update(self._parser.parse_args())
            resource_instance = bound_resource()

            return self._fn.__call__(resource_instance, item_or_items, *args, **kwargs)


def action(method='POST', collection=False):
    def wrapper(fn):
        return wraps(fn)(Action(fn, method, collection))
    return wrapper


#
#
# class Resource(object):
#
#     @action('GET', collection=True)
#     def action(self):
#         pass
#
#     @action.POST
#     def action(self):
#         pass





class Relationship(Leaf):
    def __init__(self, resource, name=None, **kwargs):
        super(Relationship, self).__init__(kwargs.pop('methods', ['GET', 'POST', 'DELETE']))
        self.resource = resource

    def get_api_routes(self):
        return super(Relationship, self).get_api_routes()
        # TODO targetSchema etc.


class ResourceMeta(MethodViewType):

    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)

        if hasattr(class_, '_meta'):
            try:
                meta = dict(getattr(class_, 'Meta').__dict__)  # copy mappingproxy into dict.
            except AttributeError:
                meta = {}

            class_.endpoint = endpoint = meta.get('resource_name', class_.__name__).lower()
            class_._children = children = {}
            class_._meta = meta

            class_._url_rule_id = meta.get('url_rule_id', '{}_id'.format(endpoint))

            for name, m in six.iteritems(members):
                if isinstance(m, Resource) and m.up:
                    raise ValueError('Attempted to change parent of {} from {} to {}'.format(m.endpoint,
                                                                                             m.up.endpoint,
                                                                                             endpoint))

                if isinstance(m, (RelationshipField, Resource, Leaf)):
                    m.up_resource = class_
                    if m.relationship_name is None:
                        m.relationship_name = name

                if isinstance(m, (Resource, Leaf)):
                    children[m.relationship_name] = m


class Resource(six.with_metaclass(ResourceMeta, flask.ext.restful.Resource)):
    storage = None
    endpoint = None
    up = None

    _meta = None
    _url_rule_id = None

    def get(self, stack):
        up, stack = pop(stack)

        if up.id is None:
            item_list = self.get_item_list(stack)
            return self.marshal_item_list(item_list, stack)
        else:
            item = self.get_item(up.id, stack)
            return self.marshal_item(item, stack)

    def post(self, stack):
        up, stack = pop(stack)

        if up.id is None:

            return self.marshal_item(self.create_item(self.request_parse_item()))

            # TODO support embeddables.
        else:


            return self.marshal_item(self.update_item(id, self.request_parse_item()))



    def get_item(self, id_, stack=None):
        raise NotImplementedError()

    def get_item_list(self, stack=None, pagination=None):
        raise NotImplementedError()

    def add_item_to_relationship(self, item, stack):
        raise NotImplementedError()

    def remove_items_from_relationship(self, item, stack):
        raise NotImplementedError()

    def create_item(self, args, stack=None):
        raise NotImplementedError()

    def update_item(self, id_, changes, patch=False, stack=None):
        raise NotImplementedError()

    def delete_item(self, id_, stack=None):
        raise NotImplementedError()

    def request_parse_item(self, limit_fields=None):
        """
        Helper method to parse an item from the request.

        :param limit_fields: optional list of field names to parse; if not set, all fields will be parsed.
        """
        parser = reqparse.RequestParser(argument_class=PresstArgument)

        for name in limit_fields or self._fields: # FIXME handle this in PresstArgument.
            if name not in self._read_only_fields:
                required = name in self._required_fields
                parser.add_argument(name, type=self._fields[name], required=required, ignore=not required)

        return parser.parse_args()


    @classmethod
    def item_get_id(cls, item):
        pass

    @classmethod
    def item_get_resource_uri(cls, item, stack):
        """Returns the `resource_uri` of an item.

        .. seealso:: :meth:`item_get_id()`
        """
        kwargs = dict((resource._url_rule_id, id) for resource, relationship_name, id in stack)
        kwargs[cls._url_rule_id] = cls.item_get_id(item)
        return url_for(cls.endpoint, **kwargs)

    @classmethod
    def marshal_item(cls, item, stack=None):
        """
        Marshals the item using the resource fields and returns a JSON-compatible dictionary.
        """
        marshaled = {'resource_uri': cls.item_get_resource_uri(item)}
        marshaled.update(marshal(item, cls._fields))
        return marshaled

    @classmethod
    def marshal_item_list(cls, items, stack=None):
        """
        Marshals a list of items from the resource.

        .. seealso:: :meth:`marshal_item`
        """
        return list(cls.marshal_item(item, stack) for item in items)


    @classmethod
    def get_api_routes(cls):
        if cls.up is None:
            up_route = ''
            up_args = ()
        else:
            up_route, up_args, _ = cls.up.get_uri_routes()['self']

        instances_uri = '/{}'.format(cls.endpoint)
        uri = '{}/<{}_id:{}>'.format(cls.endpoint, cls.endpoint, cls._meta.id_converter)
        arg = '{}_id'.format(cls.endpoint)

        return {
            'instances': (''.join((up_route, instances_uri)), up_args, ['GET', 'POST']),
            'self': (''.join((up_route, uri)), up_args + (cls, arg), ['GET', 'POST', 'PATCH', 'DELETE'])
        }

    @classmethod
    def _stack_args(cls):
        if cls.up is None:
            return (cls, cls._stack_id())
        cls.up._stack_args() + (cls, cls._stack_id())

    @classmethod
    def _stack_key(cls):
        return '{}_id'.format(cls.endpoint)

    def get_schema(self):
        # fields
        # links
        pass

    class Meta:
        store = MemoryStore


class Api(flask.ext.restful.Api):

    def __init__(self, *args, **kwargs):
        super(Api, self).__init__(*args, **kwargs)
        self._presst_resources = {}
        self._presst_resource_insts = {}
        self._model_resource_map = {}
        self.has_schema = False

    @staticmethod
    def _make_stack(stack_args, args):
        return tuple(Up(cls, None, args.pop(arg, None)) for cls, arg in stack_args)

    def output(self, resource):
        """Wraps a resource (as a flask view function), for cases where the
        resource does not directly return a response object

        :param resource: The resource as a flask view function
        """
        @wraps(resource)
        def wrapper(*args, stack_args=None, **kwargs):
            if stack_args is not None:
                kwargs['stack'] = self._make_stack(stack_args, kwargs)

            resp = resource(*args, **kwargs)
            if isinstance(resp, ResponseBase):  # There may be a better way to test
                return resp
            data, code, headers = unpack(resp)
            return self.make_response(data, code, headers=headers)
        return wrapper

    def add_resource(self, resource, *urls, **kwargs):
        # Fallback to Flask-RESTful `add_resource` implementation with regular resources:
        if not issubclass(resource, Resource):
            super(Api, self).add_resource(resource, *urls, **kwargs)

        # skip resources that have already been (auto-)imported.
        if resource in self._presst_resources.values():
            return

        resource_name = resource.endpoint

        urls = [uri for uri, ids, methods in resource.get_api_routes()]

        self._presst_resources[resource_name] = resource

        # if issubclass(resource, ModelResource):
        #     self._model_resource_map[resource.get_model()] = resource

        for name, child in six.iteritems(resource.children):
            child.endpoint = '{0}_{1}'.format(resource.endpoint, name)
            child_view_func = self.output(child.view_factory(child.endpoint, resource))

            # TODO adapt and use Api._register_view() for blueprint support

            for uri, ids, methods in child.get_api_routes().values():
                rule = self._complete_url(uri, '')

                self.app.add_url_rule(rule,
                                      view_func=child_view_func,
                                      endpoint=child.endpoint,
                                      methods=child.methods,
                                      stack_args=ids,
                                      **kwargs)

        super(Api, self).add_resource(resource, *urls, endpoint=resource_name, **kwargs)
