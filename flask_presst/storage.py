from collections import namedtuple
from urllib import request
from flask import current_app
import flask
from flask.ext.restful import abort
from flask.ext.sqlalchemy import get_state
from flask.views import MethodViewType
import six
from sqlalchemy.orm import object_session
from sqlalchemy.orm.exc import NoResultFound
from flask.ext.presst import PresstArgument
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



class ResourceMeta(MethodViewType):

    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)



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

        self.id_field = current_app.config.get('PRESST_DEFAULT_ID_FIELD', 'id')
        self.id_converter = current_app.config.get('PRESST_DEFAULT_ID_CONVERTER', 'int')

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

class PresstResource(six.with_metaclass(ResourceMeta, flask.ext.restful.Resource)):
    resource_name = None
    _parent = None
    _meta = None

    def get(self, **kwargs):




    def _make_stack(self):
        pass

    def get_uri_routes(self):
        return [
            ('/{}'.format(self.resource_name), None, ['GET', 'POST']),
            ('{}/<{}_id:{}>'.format(self.resource_name, self.resource_name, self._meta.pk_converter), None, ['GET', 'POST', 'PATCH', 'DELETE'])
        ]
