import inspect
import datetime
from flask import request, current_app
from flask.ext.restful import reqparse, Resource, abort, marshal
from flask.ext.restful import fields as restful_fields
from flask.ext.sqlalchemy import BaseQuery, Pagination
from flask.views import MethodViewType
from sqlalchemy.databases import postgres
from sqlalchemy.orm import class_mapper
from flask.ext.presst.fields import BaseRelationshipField, ArrayField, KeyValueField
from flask.ext.presst.nested import NestedProxy
from flask.ext.presst.parsing import PresstArgument
import six


LINK_HEADER_FORMAT_STR = '<{0}?page={1}&per_page={2}>; rel="{3}"'


class PresstResourceMeta(MethodViewType):
    #_instances = {}

    def __new__(mcs, name, bases, members):
        #class_ = type.__new__(mcs, name, bases, members)
        class_ = super(PresstResourceMeta, mcs).__new__(mcs, name, bases, members)

        for name, m in members.iteritems():
            if isinstance(m, (BaseRelationshipField, NestedProxy)):
                m.bound_resource = class_
            # if issubclass(m, _RelationshipResource) and not m.relationship_name:
                if m.relationship_name is None:
                    m.relationship_name = name

        if hasattr(class_, '_setup_resource'):
            try:
                meta = getattr(class_, 'Meta').__dict__
            except AttributeError:
                meta = {}

            class_._setup_resource(meta, members)

        return class_

    # def __call__(cls, *args, **kwargs):
    #     if cls not in cls._instances:
    #         cls._instances[cls] = super(PresstResourceMeta, cls).__call__(*args, **kwargs)
    #     return cls._instances[cls]


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

    @classmethod
    def _setup_resource(cls, meta, members):
        cls.nested_types = nested_types = {}
        cls._fields = fields = {}
        for name, m in members.iteritems():
            if isinstance(m, NestedProxy):
                nested_types[m.relationship_name] = m
            if isinstance(m, restful_fields.Raw):
                fields[m.attribute or name] = m

        cls._meta = meta

        field_selector = lambda m: not(inspect.isroutine(m)) and isinstance(m, restful_fields.Raw)

        cls.resource_name = meta.get('resource_name', cls.__name__).lower()

        cls._id_field = meta.get('id_field', 'id')
        cls._fields = dict(inspect.getmembers(cls, field_selector)) # TODO simplify using `members`
        cls._required_fields = meta.get('required_fields', [])

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
            return self.marshal_item(self.create_item(self.request_parse_item(request)))
        else:
            return self.marshal_item(self.update_item(id, self.request_parse_item(request)))

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
        raise NotImplementedError()

    @classmethod
    def item_get_resource_uri(cls, item):
        if cls.api is None:
            raise RuntimeError("{} has not been registered as an API endpoint.".format(cls.__name__))
        return u'{0}/{1}/{2}'.format(cls.api.prefix, cls.resource_name, unicode(item[cls._id_field])) # FIXME handle both item and attr.

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
            parser.add_argument(name, type=self._fields[name])

        return parser.parse_args()


class PolymorphicMixin(object):
    """
    :class:`PolymorphicMixin` only works in with a :class:`PresstResource`.
    """
    def marshal_item(self, item):
        resource = self.api.get_resource_for_model(item.__class__)
        marshaled = super(PolymorphicMixin, self).marshal_item(item)

        if resource and resource != self.__class__:
            marshaled[resource.resource_name.replace('/', '__')] = resource.marshal_object(item)

        # fallback:
        return marshaled


class ModelResource(PresstResource):
    _processors = ()
    _field_types = None
    _model = None

    @classmethod
    def _setup_resource(cls, meta, members):
        cls._model = model = meta.get('model', None)
        cls._processors = meta.get('processors', cls._processors)

        if not model: return
        mapper = class_mapper(model)

        # TODO support multiple primary keys with child resources.
        assert len(mapper.primary_key) == 1
        cls._id_field = mapper.primary_key[0].name

        cls._field_types = field_types = {}

        include_fields = meta.get('include_fields', None)
        exclude_fields = meta.get('exclude_fields', None)

        for name, column in dict(mapper.columns).iteritems():

            if (include_fields and name in include_fields) or \
                    (exclude_fields and name not in exclude_fields) or \
                    not (include_fields or exclude_fields):

                if meta.get('exclude_polymorphic', False) and column.table != mapper.tables[-1]:
                    continue

                if column.primary_key or column.foreign_keys:
                    continue

                if isinstance(column.type, postgres.ARRAY):
                    field_type = list
                elif isinstance(column.type, (postgres.HSTORE, postgres.JSON)):
                    field_type = dict
                else:
                    field_type = column.type.python_type

                field_types[name] = field_type

                # Add to list of fields.
                if not name in cls._fields:
                    field_class = cls._get_field_from_python_type(field_type)

                    cls._fields[name] = field_class(default=column.default)

                    if not (column.nullable or column.default):
                        cls._required_fields.append(name)

    @staticmethod
    def _get_field_from_python_type(python_type):
        return {
            str: restful_fields.String,
            unicode: restful_fields.String,
            int: restful_fields.Integer,
            bool: restful_fields.Boolean,
            list: ArrayField,
            dict: KeyValueField,
            datetime.date: restful_fields.DateTime,
            datetime.datetime: restful_fields.DateTime # TODO extend with JSON, dict (HSTORE) etc.
        }[python_type]

    @classmethod
    def _apply_processors(cls, event, *args):
        for processor in cls._processors:
            getattr(processor, event)(*args + (cls,))

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

        for processor in cls._processors:
            query = processor.filter(request.method, query, cls)

        return query

    @classmethod
    def get_item_list_for_relationship(cls, relationship, parent_item):
        query = getattr(parent_item, relationship)

        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        for processor in cls._processors:
            query = processor.filter(request.method, query, cls)

        return query

    @classmethod
    def get_item_for_id(cls, id_):
        return cls.get_item_list().get_or_404(id)

    @classmethod
    def create_item(cls, dct):
        item = cls._model()

        for key, value in dct.iteritems():
            setattr(item, key, value)

        for processor in cls._processors:
            processor.before_create_object(item, cls)

        current_app.db.session.add(item)
        current_app.session.commit()
        return item

    @classmethod
    def update_item(cls, id_, dct, partial=False):
        item = cls.get_item_for_id(id_)

        for key, value in dct.iteritems():
            setattr(item, key, value)

        try:
            for processor in cls._processors:
                processor.before_update_object(item, dct, partial, cls)

            current_app.db.session.commit()
        except:
            current_app.db.session.rollback()
            raise

    @classmethod
    def delete_item(cls, id_):
        item = cls.get_item_for_id(id_)

        for processor in cls._processors:
            processor.before_delete_object(item, cls)

        current_app.db.session.delete(item)
        current_app.db.session.commit()

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

            response = cls.api.make_response(cls.marshal_item_list(item_list.items), 200)
            response.headers['Link'] = ','.join(map(LINK_HEADER_FORMAT_STR.format, links))
            return response

        # fallback:
        return super(ModelResource).marshal_item_list(item_list)
