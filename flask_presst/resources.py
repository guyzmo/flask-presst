import datetime
from flask import request, current_app
from flask.ext.restful import reqparse, Resource, abort, marshal
from flask.ext.restful.fields import Boolean, String, Integer, DateTime, Raw
from flask.ext.sqlalchemy import BaseQuery, Pagination, get_state
from flask.views import MethodViewType
from sqlalchemy.dialects import postgres
from sqlalchemy.orm import class_mapper
from flask.ext.presst.processor import ProcessorSet
from flask_presst.fields import RelationshipFieldBase, Array, KeyValue
from flask_presst.nested import NestedProxy
from flask_presst.parsing import PresstArgument
import six


LINK_HEADER_FORMAT_STR = '<{0}?page={1}&per_page={2}>; rel="{3}"'


class PresstResourceMeta(MethodViewType):
    def __new__(mcs, name, bases, members):
        class_ = super(PresstResourceMeta, mcs).__new__(mcs, name, bases, members)

        if hasattr(class_, '_meta'):
            try:
                meta = getattr(class_, 'Meta').__dict__
            except AttributeError:
                meta = {}

            class_.resource_name = meta.get('resource_name', class_.__name__).lower()
            class_.nested_types = nested_types = {}
            class_._id_field = meta.get('id_field', 'id')
            class_._required_fields = meta.get('required_fields', [])
            class_._fields = fields = dict()
            class_._meta = meta

            for name, m in six.iteritems(members):
                if isinstance(m, (RelationshipFieldBase, NestedProxy)):
                    m.bound_resource = class_
                    if m.relationship_name is None:
                        m.relationship_name = name

                if isinstance(m, NestedProxy):
                    nested_types[m.relationship_name] = m
                elif isinstance(m, Raw):
                    fields[m.attribute or name] = m

        return class_


class PresstResource(six.with_metaclass(PresstResourceMeta, Resource)):
    """

    """
    api = None
    resource_name = None
    nested_types = None

    _meta = None
    _id_field = None
    _fields = None
    _required_fields = None

    def get(self, id=None, route=None, **kwargs):
        if route:
            try:
                nested_type = self.nested_types[route]

                if (id is None) != nested_type.collection:
                    abort(404)

                return nested_type.dispatch_request(self, id)
            except KeyError:
                abort(404)
        elif id is None:
            item_list = self.get_item_list()
            return self.marshal_item_list(item_list)
        else:
            item = self.get_item_for_id(id)
            return self.marshal_item(item)

    def post(self, id=None, route=None, **kwargs):
        if route:
            try:
                nested_type = self.nested_types[route]

                if (id is None) != nested_type.collection:
                    abort(404)

                return nested_type.dispatch_request(self, id)
            except KeyError:
                abort(404)
        elif id is None:
            return self.marshal_item(self.create_item(self.request_parse_item()))
        else:
            return self.marshal_item(self.update_item(id, self.request_parse_item()))

    def patch(self, id, route=None):
        if id is None:
            abort(400, message='PATCH is not permitted on collections.')
        if route:
            try:
                nested_type = self.nested_types[route]

                if (id is None) != nested_type.collection:
                    abort(404)

                return nested_type.dispatch_request(self, id)
            except KeyError:
                abort(404)
        else:
            # TODO consider abort(400) if request.JSON is not a dictionary.
            changes = self.request_parse_item(limit_fields=(name for name in self._fields if name in request.json))
            return self.marshal_item(self.update_item(id, changes, partial=True))

    def delete(self, id, route=None, **kwargs):
        if id is None:
            abort(400, message='DELETE is not permitted on collections.')
        if route:
            try:
                nested_type = self.nested_types[route]

                if (id is None) != nested_type.collection:
                    abort(404)

                return nested_type.dispatch_request(self, id)
            except KeyError:
                abort(404)
        else:
            self.delete_item(id)
            return None, 204

    @classmethod
    def get_item_for_id(cls, id_):
        raise NotImplementedError()

    @classmethod
    def get_item_list(cls):
        raise NotImplementedError()

    @classmethod
    def get_item_list_for_relationship(cls, relationship, parent_item):
        raise NotImplementedError()

    @classmethod
    def create_item_relationship(cls, id_, relationship, parent_item):
        raise NotImplementedError()

    @classmethod
    def delete_item_relationship(cls, id_, relationship, parent_item):
        raise NotImplementedError()

    @classmethod
    def create_item(cls, dct):
        """This method must either return the created item or abort with the appropriate error."""
        raise NotImplementedError()

    @classmethod
    def update_item(cls, id_, dct, partial=False):
        "This method must either return the updated item or abort with the appropriate error."
        raise NotImplementedError()

    @classmethod
    def delete_item(cls, id_):
        "This method must either return None (nothing) or abort with the appropriate error."
        raise NotImplementedError()

    @classmethod
    def item_get_resource_uri(cls, item):
        if cls.api is None:
            raise RuntimeError("{} has not been registered as an API endpoint.".format(cls.__name__))
        return '{0}/{1}/{2}'.format(cls.api.prefix, cls.resource_name, six.text_type(getattr(item, cls._id_field, None) or item[cls._id_field])) # FIXME handle both item and attr.

    @classmethod
    def marshal_item(cls, item):
        marshaled = {'resource_uri': cls.item_get_resource_uri(item)}
        marshaled.update(marshal(item, cls._fields))
        return marshaled

    @classmethod
    def marshal_item_list(cls, items):
        return list(cls.marshal_item(item) for item in items)

    def request_parse_item(self, limit_fields=None):
        parser = reqparse.RequestParser(argument_class=PresstArgument)

        for name in limit_fields or self._fields: # FIXME handle this in PresstArgument.
            parser.add_argument(name, type=self._fields[name], required=name in self._required_fields)

        return parser.parse_args()


class ModelResourceMeta(PresstResourceMeta):
    def __new__(mcs, name, bases, members):
        class_ = super(ModelResourceMeta, mcs).__new__(mcs, name, bases, members)
        meta = class_._meta

        if meta:
            class_._model = model = meta.get('model', None)
            class_._processors = ProcessorSet(meta.get('processors', ()))

            if not model:
                return class_

            mapper = class_mapper(model)

            # TODO support multiple primary keys with child resources.
            assert len(mapper.primary_key) == 1

            class_._id_field = meta.get('id_field', mapper.primary_key[0].name)
            class_._field_types = field_types = {}

            class_.resource_name = meta.get('resource_name', model.__tablename__).lower()

            fields, required_fields = class_._fields, class_._required_fields

            include_fields = meta.get('include_fields', None)
            exclude_fields = meta.get('exclude_fields', None)

            for name, column in six.iteritems(dict(mapper.columns)):
                if (include_fields and name in include_fields) or \
                        (exclude_fields and name not in exclude_fields) or \
                        not (include_fields or exclude_fields):

                    if meta.get('exclude_polymorphic', False) and column.table != mapper.tables[-1]:
                        continue

                    if column.primary_key or column.foreign_keys:
                        continue

                    if isinstance(column.type, postgres.ARRAY):
                        field_type = list
                    elif isinstance(column.type, postgres.HSTORE):
                        field_type = dict
                    # TODO postgres.JSON case, backwards compatibility.
                    else:
                        field_type = column.type.python_type

                    field_types[name] = field_type

                    # Add to list of fields.
                    if not name in fields:
                        field_class = class_._get_field_from_python_type(field_type)

                        # TODO implement support for ColumnDefault
                        # fields[name] = field_class(default=column.default)
                        fields[name] = field_class()

                        if not (column.nullable or column.default):
                            required_fields.append(name)
        return class_


class ModelResource(six.with_metaclass(ModelResourceMeta, PresstResource)):
    _model = None
    _processors = ProcessorSet()
    _field_types = None

    @staticmethod
    def _get_field_from_python_type(python_type):
        return {
            str: String,
            six.text_type: String,
            int: Integer,
            bool: Boolean,
            list: Array,
            dict: KeyValue,
            datetime.date: DateTime,
            datetime.datetime: DateTime # TODO extend with JSON, dict (HSTORE) etc.
        }[python_type]

    @classmethod
    def _get_session(cls):
        return get_state(current_app).db.session

    @classmethod
    def get_model(cls):
        return cls._model

    @classmethod
    def get_item_list(cls):
        """
        Pagination is only supported for resources accessed through :class:`Relationship` if
        the relationship to the parent is `lazy='dynamic'`.
        """
        query = cls._model.query

        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        cls._processors.filter(request.method, query, cls)
        return query

    @classmethod
    def get_item_list_for_relationship(cls, relationship, parent_item):
        query = getattr(parent_item, relationship)

        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        cls._processors.filter(request.method, query)
        return query

    @classmethod
    def create_item_relationship(cls, id_, relationship, parent_item):
        item = cls.get_item_for_id(id_)

        cls._processors.before_create_relationship(parent_item, relationship, item)

        getattr(parent_item, relationship).append(item)

        cls._processors.after_create_relationship(parent_item, relationship, item)

    @classmethod
    def delete_item_relationship(cls, id_, relationship, parent_item):
        item = cls.get_item_for_id(id_)

        cls._processors.before_delete_relationship(parent_item, relationship, item)

        getattr(parent_item, relationship).remove(item)

        cls._processors.after_delete_relationship(parent_item, relationship, item)

    @classmethod
    def get_item_for_id(cls, id_):
        return cls.get_item_list().get_or_404(id_)

    @classmethod
    def create_item(cls, dct):
        # noinspection PyCallingNonCallable
        item = cls._model()
        for key, value in six.iteritems(dct):
            setattr(item, key, value)

        cls._processors.before_create_item(item, cls)

        session = cls._get_session()

        try:
            session.add(item)
            session.commit()
        except:
            session.rollback()
            raise

        cls._processors.after_create_item(item, cls)
        return item

    @classmethod
    def update_item(cls, id_, dct, partial=False):
        item = cls.get_item_for_id(id_)

        for key, value in six.iteritems(dct):
            setattr(item, key, value)

        session = cls._get_session()

        try:
            cls._processors.before_update_item(item, dct, partial, cls)
            session.commit()
        except:
            session.rollback()
            raise

        cls._processors.after_update_item(item, cls)
        return item

    @classmethod
    def delete_item(cls, id_):
        item = cls.get_item_for_id(id_)

        cls._processors.before_delete_item(item, cls)

        session = cls._get_session()
        session.delete(item)
        session.commit()

        cls._processors.after_delete_item(item, cls)

    _pagination_parser = reqparse.RequestParser()
    _pagination_parser.add_argument('per_page', location='args', type=int, default=20) # 20
    _pagination_parser.add_argument('page', location='args', type=int, default=1)

    @classmethod
    def marshal_item_list(cls, item_list, paginate=True):
        """
        Like :meth:`PrestoResource.marshal_item_list()` except that :attr:`object_list`
        can be a :class:`Pagination` object, in which case a paginated result will be returned.
        """
        if isinstance(item_list, BaseQuery):
            if paginate:
                args = cls._pagination_parser.parse_args()
                item_list = item_list.paginate(page=args.page, per_page=args.per_page)
            else:
                item_list = item_list.all()

        if isinstance(item_list, Pagination):
            links = [(request.path, item_list.page, item_list.per_page, 'self')]

            if item_list.has_prev:
                links.append((request.path, 1, item_list.per_page, 'first'))
                links.append((request.path, item_list.page - 1, item_list.per_page, 'prev'))
            if item_list.has_next:
                links.append((request.path, item_list.pages, item_list.per_page, 'last'))
                links.append((request.path, item_list.page + 1, item_list.per_page, 'next'))

            headers = {'Link': ','.join((LINK_HEADER_FORMAT_STR.format(*link) for link in links))}
            return super(ModelResource, cls).marshal_item_list(item_list.items), 200, headers

        # fallback:
        return super(ModelResource, cls).marshal_item_list(item_list)


class PolymorphicModelResource(ModelResource):
    """
    :class:`PolymorphicMixin` only works in with a :class:`PresstResource`.
    """

    @classmethod
    def marshal_item(cls, item):
        resource = cls.api.get_resource_for_model(item.__class__)
        marshaled = super(PolymorphicModelResource, cls).marshal_item(item)

        if resource and resource != cls:
            marshaled[resource.resource_name.replace('/', '__')] = resource.marshal_item(item)

        # fallback:
        return marshaled