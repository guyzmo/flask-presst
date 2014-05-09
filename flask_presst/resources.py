import datetime
from flask import request, current_app, _request_ctx_stack
from flask.ext.restful import reqparse, Resource, abort, marshal
from flask.ext.restful.fields import Boolean, String, Integer, DateTime, Raw
from flask.ext.sqlalchemy import BaseQuery, Pagination, get_state
from flask.views import MethodViewType
from sqlalchemy.dialects import postgres
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import NoResultFound
from flask_presst.signals import before_create_item, after_create_item, before_create_relationship, \
    after_create_relationship, before_delete_relationship, after_delete_relationship, before_update_item, \
    before_delete_item, after_delete_item, after_update_item, on_filter_read, on_filter_update, \
    on_filter_delete
from flask_presst.fields import _RelationshipField, Array, KeyValue, Date, JSON
from flask_presst.nesting import NestedProxy
from flask_presst.parsing import PresstArgument
import six


LINK_HEADER_FORMAT_STR = '<{0}?page={1}&per_page={2}>; rel="{3}"'


class PresstResourceMeta(MethodViewType):
    def __new__(mcs, name, bases, members):
        class_ = super(PresstResourceMeta, mcs).__new__(mcs, name, bases, members)

        if hasattr(class_, '_meta'):
            try:
                meta = dict(getattr(class_, 'Meta').__dict__)  # copy mappingproxy into dict.
            except AttributeError:
                meta = {}

            class_.resource_name = meta.get('resource_name', class_.__name__).lower()
            class_.nested_types = nested_types = {}
            class_._id_field = meta.get('id_field', 'id')
            class_._required_fields = meta.get('required_fields', [])
            class_._fields = fields = dict()
            class_._read_only_fields = set(meta.get('read_only_fields', []))
            class_._meta = meta

            for name, m in six.iteritems(members):
                if isinstance(m, (_RelationshipField, NestedProxy)):
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

    Resource item property fields are defined as as class attributes. e.g.:

    .. code-block:: python

        class PersonResource(PresstResource):
            name = fields.String()
            age = fields.Integer()
            # ...

    Each new subclass of :class:`PresstResource` can be configured using a class attribute, :class:`Meta`, which
    includes properties that are applied at creation time by the :class:`PresstResource`'s metaclass. The following
    attributes can be declared within :class:`Meta`:

    =====================  ==============================================================================
    Attribute name         Description
    =====================  ==============================================================================
    resource_name          The name of the resource used to build the resource endpoint, also used
                           for referencing the resource using e.g. :class:`fields.ToMany`. *Default:
                           the lower-case of the class name of the resource*
    id_field               The default implementation of :class:`PresstResource` attempts to read the id
                           of each resource item using this attribute or item key. The id field will
                           never be marshalled [#f1]_. *Default: 'id'*
    required_fields        A list of fields that must be given in `POST` requests.
    read_only_fields       A list of fields that are returned by the resource but are ignored in `POST`
                           and `PATCH` requests.
    =====================  ==============================================================================

    .. rubric:: Footnotes

    .. [#f1] Adventurous people can override :meth:`marshal_item` to include `id_field` instead of or in addition to
       ``'resource_uri'``.

    """
    api = None
    resource_name = None
    nested_types = None

    _meta = None
    _id_field = None
    _fields = None
    _read_only_fields = None
    _required_fields = None

    def get(self, id=None, **kwargs):
        if id is None:
            item_list = self.get_item_list()
            return self.marshal_item_list(item_list)
        else:
            item = self.get_item_for_id(id)
            return self.marshal_item(item)

    def post(self, id=None, *args, **kwargs):
        if id is None:
            return self.marshal_item(self.create_item(self.request_parse_item()))
        else:
            return self.marshal_item(self.update_item(id, self.request_parse_item()))

    def patch(self, id):
        if id is None:
            abort(400, message='PATCH is not permitted on collections.')
        else:
            # TODO consider abort(400) if request.JSON is not a dictionary.
            changes = self.request_parse_item(limit_fields=(name for name in self._fields if name in request.json))
            return self.marshal_item(self.update_item(id, changes, partial=True))

    def delete(self, id, *args, **kwargs):
        if id is None:
            abort(400, message='DELETE is not permitted on collections.')
        else:
            self.delete_item(id)
            return None, 204

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
    def get_item_list_for_relationship(cls, relationship, parent_item):  # pragma: no cover
        """
        Return the list of items for a relationship. Must be implemented in nested resources.

        :param str relationship: name of the relationship in the parent level resource
        :param parent_item: instance of the item from the parent level resource
        """
        raise NotImplementedError()

    @classmethod
    def create_item_relationship(cls, id_, relationship, parent_item):  # pragma: no cover
        """
        Add an item to a relationship. Must be implemented in nested resources.

        :param id_: the id of the item to add to the relationship
        :param str relationship: name of the relationship in the parent level resource
        :param parent_item: instance of the item from the parent level resource
        """
        raise NotImplementedError()

    @classmethod
    def delete_item_relationship(cls, id_, relationship, parent_item):  # pragma: no cover
        """
        Delete an item from a relationship. Must be implemented in nested resources.

        :param id_: the id of the item to remove from the relationship
        :param str relationship: name of the relationship in the parent level resource
        :param parent_item: instance of the item from the parent level resource
        """
        raise NotImplementedError()

    @classmethod
    def create_item(cls, dct):  # pragma: no cover
        """
        Must be implemented to create a new item in the resource collection.

        :param dict dct: parsed resource fields
        :return: the new item
        """
        raise NotImplementedError()

    @classmethod
    def update_item(cls, id_, dct, partial=False):  # pragma: no cover
        """
        Must be implemented to update an item in the resource collection.

        :param id_: id of the item to update
        :param dict dct: dictionary of changes
        :param bool partial: whether this is a `PATCH` change
        """
        raise NotImplementedError()

    @classmethod
    def delete_item(cls, id_):  # pragma: no cover
        """
        Must be implemented to delete an item from the resource collection.

        :param id_: id of the item to delete
        """
        raise NotImplementedError()

    @classmethod
    def item_get_resource_uri(cls, item):
        """Returns the `resource_uri` of an item.

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
        marshaled = {'resource_uri': cls.item_get_resource_uri(item)}
        marshaled.update(marshal(item, cls._fields))
        return marshaled

    @classmethod
    def marshal_item_list(cls, items):
        """
        Marshals a list of items from the resource.

        .. seealso:: :meth:`marshal_item`
        """
        return list(cls.marshal_item(item) for item in items)

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


class ModelResourceMeta(PresstResourceMeta):
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

                    field_class = None

                    if meta.get('exclude_polymorphic', False) and column.table != mapper.tables[-1]:
                        continue

                    if column.primary_key or column.foreign_keys:
                        continue

                    if isinstance(column.type, postgres.ARRAY):
                        field_type = list
                    elif isinstance(column.type, postgres.HSTORE):
                        field_type = dict
                        field_class = KeyValue
                    elif hasattr(postgres, 'JSON') and isinstance(column.type, postgres.JSON):
                        field_type = lambda data: data
                        field_class = JSON
                    else:
                        field_type = column.type.python_type

                    field_types[name] = field_type

                    # Add to list of fields.
                    if not name in fields:
                        if not field_class:
                            field_class = class_._get_field_from_python_type(field_type)

                        # TODO implement support for ColumnDefault
                        # fields[name] = field_class(default=column.default)
                        fields[name] = field_class()

                        if not (column.nullable or column.default):
                            required_fields.append(name)
        return class_


class ModelResource(six.with_metaclass(ModelResourceMeta, PresstResource)):
    """

    :class:`ModelResource` inherits all of the :class:`Meta` options of :class:`PresstResource`, however
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


    This resource class processes all of the signals in :mod:`flask.ext.presst.signals`.
    """
    _model = None
    _model_id_column = None
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
    def _process_filter_signal(cls, query, **kwargs):
        if request.method in ('HEAD', 'GET'):
            signal = on_filter_read
        elif request.method in ('POST', 'PATCH'):
            signal = on_filter_update
        elif request.method in ('DELETE',):
            signal = on_filter_delete
        else:
            return query

        for _, response in signal.send(cls, **kwargs):
            if callable(response):
                query = response(query)

        return query

    @classmethod
    def get_item_list(cls):
        """
        Pagination is only supported for resources accessed through :class:`Relationship` if
        the relationship to the parent is `lazy='dynamic'`.
        """
        query = cls._model.query

        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        return cls._process_filter_signal(query)

    @classmethod
    def get_item_list_for_relationship(cls, relationship, parent_item):
        query = getattr(parent_item, relationship)

        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        return cls._process_filter_signal(query)

    @classmethod
    def create_item_relationship(cls, id_, relationship, parent_item):
        item = cls.get_item_for_id(id_)

        before_create_relationship.send(cls,
                                        parent_item=parent_item,
                                        relationship=relationship,
                                        item=item)

        session = cls._get_session()

        try:
            getattr(parent_item, relationship).append(item)
            session.commit()
        except:
            session.rollback()
            raise

        after_create_relationship.send(cls,
                                       parent_item=parent_item,
                                       relationship=relationship,
                                       item=item)
        return item

    @classmethod
    def delete_item_relationship(cls, id_, relationship, parent_item):
        item = cls.get_item_for_id(id_)

        before_delete_relationship.send(cls,
                                        parent_item=parent_item,
                                        relationship=relationship,
                                        item=item)

        session = cls._get_session()

        try:
            getattr(parent_item, relationship).remove(item)
            session.commit()
        except:
            session.rollback()
            raise

        after_delete_relationship.send(cls,
                                       parent_item=parent_item,
                                       relationship=relationship,
                                       item=item)

    @classmethod
    def get_item_for_id(cls, id_):
        try:  # SQLAlchemy's .get() does not work well with .filter()
            return cls.get_item_list().filter(cls._model_id_column == id_).one()
        except NoResultFound:
            abort(404)

    @classmethod
    def create_item(cls, dct):
        # noinspection PyCallingNonCallable
        item = cls._model()
        for key, value in six.iteritems(dct):
            setattr(item, key, value)

        before_create_item.send(cls, item=item)

        session = cls._get_session()

        try:
            session.add(item)
            session.commit()
        except:
            session.rollback()
            raise

        after_create_item.send(cls, item=item)
        return item

    @classmethod
    def update_item(cls, id_, dct, partial=False):
        item = cls.get_item_for_id(id_)

        session = cls._get_session()

        try:
            before_update_item.send(cls, item=item, changes=dct, partial=partial)

            for key, value in six.iteritems(dct):
                setattr(item, key, value)

            session.commit()
        except:
            session.rollback()
            raise

        after_update_item.send(cls, item=item)
        return item

    @classmethod
    def delete_item(cls, id_):
        item = cls.get_item_for_id(id_)

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


class PolymorphicModelResource(ModelResource):
    """
    :class:`PolymorphicModelResource` is identical to :class:`ModelResource`, except that when it marshals an item
    that has a different class than the ``model`` attribute defined in :class:`Meta`, it marshals the contents of that
    model separately from the inherited resource and adds it to the marshalled dictionary as a property with the
    name of the inherited resource.

    e.g.

    .. code-block:: javascript

        {
            "resource_uri": "/polymorphic_resource/1",
            // polymorphic_resource properties
            "base_resource": {
                "resource_uri": "/base_resource/1",
                // base_resource properties
            }
        }


    :class:`PolymorphicModelResource` is designed to be used with SQLAlchemy models that
    make use of `SQLAlchemy's polymorphic inheritance <http://docs.sqlalchemy.org/en/latest/orm/inheritance.html>`_.
    """

    @classmethod
    def marshal_item(cls, item):
        resource = cls.api.get_resource_for_model(item.__class__)
        marshaled = super(PolymorphicModelResource, cls).marshal_item(item)

        if resource and resource != cls:
            marshaled[resource.resource_name.replace('/', '__')] = resource.marshal_item(item)

        # fallback:
        return marshaled