import datetime

from flask import request, current_app
from flask_restful import reqparse, Resource as RestfulResource, abort, marshal
from flask_sqlalchemy import BaseQuery, Pagination, get_state
from flask.views import MethodViewType
from sqlalchemy.dialects import postgres
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.util import classproperty
import six

from flask_presst.routes import ResourceSchema
from flask_presst.fields import String, Integer, Boolean, List, DateTime, EmbeddedBase, Raw, KeyValue, Arbitrary, \
    Date, Number
from flask_presst.references import EmbeddedJob, ItemListWrapper, ItemWrapper
from flask_presst.signals import *
from flask_presst.routes import ResourceRoute
from flask_presst.parse import SchemaParser


LINK_HEADER_FORMAT_STR = '<{0}?page={1}&per_page={2}>; rel="{3}"'


class ResourceMeta(MethodViewType):
    def __new__(mcs, name, bases, members):
        class_ = super(ResourceMeta, mcs).__new__(mcs, name, bases, members)

        if hasattr(class_, '_meta'):
            try:
                meta = dict(getattr(class_, 'Meta').__dict__)  # copy mappingproxy into dict.
            except AttributeError:
                meta = {}

            class_.resource_name = meta.get('resource_name', class_.__name__).lower()
            class_.routes = routes = dict(getattr(class_, 'routes', {}))
            class_._id_field = meta.get('id_field', 'id')
            class_._required_fields = meta.get('required_fields', [])
            class_._fields = fields = dict()
            class_._read_only_fields = set(meta.get('read_only_fields', []))
            class_._meta = meta

            for name, m in six.iteritems(members):
                if isinstance(m, (EmbeddedBase, ResourceRoute)):
                    m.bound_resource = class_
                    if m.relationship_name is None:
                        m.relationship_name = name

                if isinstance(m, ResourceRoute):
                    routes[m.relationship_name] = m
                elif isinstance(m, Raw):
                    field_name = m.attribute or name
                    fields[field_name] = m

        return class_


class Resource(six.with_metaclass(ResourceMeta, RestfulResource)):
    """

    Resource item property fields are defined as as class attributes. e.g.:

    .. code-block:: python

        class PersonResource(Resource):
            name = fields.String()
            age = fields.Integer()
            # ...

    Each new subclass of :class:`Resource` can be configured using a class attribute, :class:`Meta`, which
    includes properties that are applied at creation time by the :class:`Resource`'s metaclass. The following
    attributes can be declared within :class:`Meta`:

    =====================  ==============================================================================
    Attribute name         Description
    =====================  ==============================================================================
    resource_name          The name of the resource used to build the resource endpoint, also used
                           for referencing the resource using e.g. :class:`fields.ToMany`. *Default:
                           the lower-case of the class name of the resource*
    id_field               The default implementation of :class:`Resource` attempts to read the id
                           of each resource item using this attribute or item key. The id field will
                           never be marshalled [#f1]_. *Default: 'id'*
    required_fields        A list of fields that must be given in `POST` requests.
    read_only_fields       A list of fields that are returned by the resource but are ignored in `POST`
                           and `PATCH` requests. Useful for e.g. timestamps.
    title                  JSON-schema title declaration
    description            JSON-schema description declaration
    =====================  ==============================================================================

    .. rubric:: Footnotes

    .. [#f1] Adventurous people can override :meth:`marshal_item` to include `id_field` instead of or in addition to
       ``'_uri'``.

    """
    api = None
    resource_name = None
    routes = {}
    route_prefix = None

    _meta = None
    _id_field = None
    _fields = None
    _relationships = None
    _read_only_fields = None
    _required_fields = None

    schema = ResourceSchema()

    def get(self, id=None, **kwargs):
        if id is None:
            return ItemListWrapper.get_list(self).marshal()
        else:
            return ItemWrapper.read(self, id).marshal()

    def post(self, id=None, *args, **kwargs):
        if id is None:
            return ItemListWrapper.create(self, request.json).marshal(), 200
        else:
            return ItemWrapper.read(self, id).update(request.json).marshal(), 200

    def patch(self, id=None):
        if id is None:
            abort(405, message='PATCH is not permitted on collections')
        else:
            return ItemWrapper.read(self, id).update(request.json, partial=True).marshal(), 200

    def delete(self, id=None, *args, **kwargs):
        if id is None:
            abort(405, message='DELETE is not permitted on collections.')
        else:
            ItemWrapper.read(self, id).delete()
            return None, 204

    @classmethod
    def get_item_from_uri(cls, value, changes=None):
        resource, id = cls.api.parse_resource_uri(value)

        if cls != resource:
            abort(400, msg='Wrong resource item type, expected {0}, got {1}'.format(
                cls.resource_name,
                resource.resource_name))

        return cls.get_item_for_id(id)

    @classproperty
    def item_parser(cls):
        return SchemaParser(cls._fields, cls._required_fields, cls._read_only_fields)

    @classmethod
    def begin(cls):
        """
        Called at the beginning of a create or update operation.
        May be a no-op.
        """
        pass

    @classmethod
    def commit(cls):
        """
        Called at the end of a create or update operation.
        Should flush all changes and fail if necessary.
        """
        pass

    def _request_get_data(self):
        # TODO upcoming in Flask 0.11: 'is_json':
        # if not request.is_json:
        #     abort(415)
        request_data = request.json

        if request_data is None:
            abort(400, message='JSON required')

        if not isinstance(request_data, (dict, list)):
            abort(400, message='JSON dictionary or array required')

        return request_data

    @classmethod
    def get_item_for_id(cls, id_):  # pragma: no cover
        """
        Must be implemented to either return the item or raise an exception such as
        :class:`werkzeug.exceptions.NotFound`.

        :param id_: id of the resource item to return
        """
        raise NotImplementedError()

    @classmethod
    def item_get_id(cls, item):
        """
        Returns the id attribute of a given item. Uses ``Meta.id_field``.
        """
        return getattr(item, cls._id_field, None) or item[cls._id_field]

    @classmethod
    def get_item_list(cls):  # pragma: no cover
        """
        Must be implemented in top-level resources to return a list of items in the collection.

        .. note::

            The term *list* here is flexible, as any type of object is valid if it can be processed by
            :meth:`marshal_item_list`. The default implementation supports any iterable. It is encouraged to implement
            some form of lazy-loading or to trim the list based on the ``request``.

        .. seealso:: :meth:`marshal_item_list`
        """
        raise NotImplementedError()

    @classmethod
    def get_relationship(cls, item, relationship):  # pragma: no cover
        """
        Return the list of items for a relationship. Must be implemented in the parents of nested resources.

        :param item: instance of the item from the parent level resource
        :param str relationship: name of the relationship from the parent resource
        """
        raise NotImplementedError()

    @classmethod
    def add_to_relationship(cls, item, relationship, child):  # pragma: no cover
        """
        Add a child item to a relationship. Must be implemented in the parents of nested resources.

        :param item: instance of the item from the parent resource
        :param str relationship: name of the relationship from the parent resource
        :param child: item to remove from the relationship
        """
        raise NotImplementedError()

    @classmethod
    def remove_from_relationship(cls, item, relationship, child):  # pragma: no cover
        """
        Delete a child item from a relationship. Must be implemented in the parents of nested resources.

        :param item: instance of the item from the parent resource
        :param str relationship: name of the relationship from the parent resource
        :param child: item to remove from the relationship
        """
        raise NotImplementedError()

    @classmethod
    def create_item(cls, dct, commit=True):  # pragma: no cover
        """
        Must be implemented to create a new item in the resource collection.

        :param dict dct: parsed resource fields
        :return: the new item
        """
        raise NotImplementedError()

    @classmethod
    def update_item(cls, item, changes, partial=False, commit=True):  # pragma: no cover
        """
        Must be implemented to update an item in the resource collection.

        :param item: item to update
        :param dict changes: dictionary of changes
        :param bool partial: whether this is a `PATCH` change
        """
        raise NotImplementedError()

    @classmethod
    def delete_item(cls, item):  # pragma: no cover
        """
        Must be implemented to delete an item from the resource collection.

        :param item: item to delete
        """
        raise NotImplementedError()

    @classmethod
    def item_get_uri(cls, item):
        """Returns the `_uri` of an item.

        .. seealso:: :meth:`item_get_id()`
        """
        if cls.api is None:
            raise RuntimeError("{} has not been registered as an API endpoint.".format(cls.__name__))
        return cls.api.url_for(cls, id=cls.item_get_id(item))

    @classmethod
    def marshal_item(cls, item):
        """
        Marshals the item using the resource fields and returns a JSON-compatible dictionary.
        """
        marshaled = {'_uri': cls.item_get_uri(item)}
        marshaled.update(marshal(item, cls._fields))
        return marshaled

    @classmethod
    def marshal_item_list(cls, items):
        """
        Marshals a list of items from the resource.

        .. seealso:: :meth:`marshal_item`
        """
        return list(cls.marshal_item(item) for item in items)


class ModelResourceMeta(ResourceMeta):
    def __new__(mcs, name, bases, members):
        class_ = super(ModelResourceMeta, mcs).__new__(mcs, name, bases, members)
        meta = class_._meta

        if meta:
            class_._model = model = meta.get('model', None)

            if not model:
                return class_

            mapper = class_mapper(model)

            # TODO support multiple primary keys with child resources.
            assert len(mapper.primary_key) == 1

            class_._id_field = meta.get('id_field', mapper.primary_key[0].name)

            if 'id_field' in meta:
                class_._model_id_column = getattr(model, meta['id_field'])
            else:
                class_._model_id_column = mapper.primary_key[0]

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
                        field_class = lambda **kw: List(String, **kw)
                    elif isinstance(column.type, postgres.HSTORE):
                        field_class = KeyValue
                    # Numeric/Decimal
                    elif hasattr(postgres, 'JSON') and isinstance(column.type, postgres.JSON):
                        field_class = Arbitrary
                    else:
                        field_class = class_._get_field_from_python_type(column.type.python_type)

                    # Add to list of fields.
                    if not name in fields:
                        default = None
                        nullable = column.nullable

                        if column.default is not None and column.default.is_scalar:
                            default = column.default.arg

                        fields[name] = field_class(default=default, nullable=nullable)

                        if not (column.nullable or column.default):
                            required_fields.append(name)
        return class_


class ModelResource(six.with_metaclass(ModelResourceMeta, Resource)):
    """

    :class:`ModelResource` inherits all of the :class:`Meta` options of :class:`Resource`, however
    with slightly different behavior and including some additions.

    =====================  ==============================================================================
    Attribute name         Description
    =====================  ==============================================================================
    model                  The :class:`sqlalchemy.ext.declarative.declarative_base` model this resource
                           maps to.
                           Tested only with `Flask-SQLAlchemy` models.
    resource_name          Now defaults to the lower-case of the model class name.
    id_field               Now defaults to the name of the primary key of `model`.
    include_fields         A list of fields that should be imported from the `model`. By default, all
                           columns other than foreign key and primary key columns are imported.
                           :func:`sqlalchemy.orm.relationship` model attributes and hybrid properties
                           cannot be defined in this way and have to be specified explicitly as resource
                           class attributes.
    exclude_fields         A list of fields that should not be imported from the `model`.
    exclude_polymorphic    Whether to exclude fields that are inherited from the parent model of a
                           polymorphic model. *Defaults to False*
    required_fields        Fields that are automatically imported from the model are automatically
                           required if their columns are not `nullable` and do not have a `default`.
    =====================  ==============================================================================


    This resource class processes all of the signals in :mod:`flask_presst.signals`.
    """
    _model = None
    _model_id_column = None

    @staticmethod
    def _get_field_from_python_type(python_type):
        return {
            str: String,
            six.text_type: String,
            int: Integer,
            float: Number,
            bool: Boolean,
            list: List,
            dict: KeyValue,
            datetime.date: Date,
            datetime.datetime: DateTime
        }[python_type]

    @classmethod
    def _get_session(cls):
        return get_state(current_app).db.session

    @classmethod
    def get_model(cls):
        return cls._model

    @classmethod
    def begin(cls):
        cls._get_session()

    @classmethod
    def commit(cls):
        # TODO handle errors
        cls._get_session().commit()

    @classmethod
    def rollback(cls):
        cls._get_session().rollback()

    @classmethod
    def get_item_list(cls):
        """
        Pagination is only supported for resources accessed through :class:`Relationship` if
        the relationship to the parent is `lazy='dynamic'`.
        """
        query = cls._model.query

        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        return query

    @classmethod
    def get_relationship(cls, item, relationship):
        query = getattr(item, relationship)

        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        # FIXME build dynamic query with backref

        return query

    @classmethod
    def add_to_relationship(cls, item, relationship, child):

        before_add_relationship.send(cls,
                                     item=item,
                                     relationship=relationship,
                                     child=child)

        getattr(item, relationship).append(child)

        after_add_relationship.send(cls,
                                    item=item,
                                    relationship=relationship,
                                    child=child)

        return child

    @classmethod
    def remove_from_relationship(cls, item, relationship, child):

        before_remove_relationship.send(cls,
                                        item=item,
                                        relationship=relationship,
                                        child=child)

        getattr(item, relationship).remove(child)

        after_remove_relationship.send(cls,
                                       item=item,
                                       relationship=relationship,
                                       child=child)

    @classmethod
    def get_item_for_id(cls, id_):
        try:  # SQLAlchemy's .get() does not work well with .filter()
            return cls.get_item_list().filter(cls._model_id_column == id_).one()
        except NoResultFound:
            abort(404)

    @classmethod
    def create_item(cls, properties, commit=True):
        # noinspection PyCallingNonCallable
        item = cls._model()

        for key, value in six.iteritems(properties):
            setattr(item, key, value)

        before_create_item.send(cls, item=item)

        session = cls._get_session()

        try:
            session.add(item)
            if commit:
                session.commit()
        except:
            session.rollback()
            raise

        after_create_item.send(cls, item=item)
        return item

    @classmethod
    def update_item(cls, item, changes, partial=False, commit=True):
        session = cls._get_session()

        try:
            before_update_item.send(cls, item=item, changes=changes, partial=partial)

            for key, value in six.iteritems(changes):
                setattr(item, key, value)

            if commit:
                session.commit()
        except:
            session.rollback()
            raise

        after_update_item.send(cls, item=item)
        return item

    @classmethod
    def delete_item(cls, item):
        before_delete_item.send(cls, item=item)

        session = cls._get_session()
        session.delete(item)
        session.commit()

        after_delete_item.send(cls, item=item)

    @classmethod
    def _parse_request_pagination(cls):
        default_per_page = current_app.config.get('PRESST_DEFAULT_PER_PAGE', 20)
        max_per_page = current_app.config.get('PRESST_MAX_PER_PAGE', 100)

        parser = reqparse.RequestParser()
        parser.add_argument('per_page', location='args', type=int, default=default_per_page)
        parser.add_argument('page', location='args', type=int, default=1)

        args = parser.parse_args()
        page, per_page = args.page, args.per_page

        if per_page > max_per_page:
            per_page = max_per_page

        return page, per_page

    @classmethod
    def marshal_item_list(cls, item_list, paginate=True):
        """
        Like :meth:`PrestoResource.marshal_item_list()` except that :attr:`object_list`
        can be a :class:`Pagination` object, in which case a paginated result will be returned.
        """
        if isinstance(item_list, BaseQuery):
            if paginate:
                page, per_page = cls._parse_request_pagination()
                item_list = item_list.paginate(page=page, per_page=per_page)
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
