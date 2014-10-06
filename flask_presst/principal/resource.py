from flask_principal import Permission, RoleNeed
from flask_restful import abort
import six
from sqlalchemy.util import classproperty
from flask_presst.resources import ModelResourceMeta
from flask_presst import ModelResource, signals
from flask_presst.fields import ToOne
from flask_presst.principal.needs import HybridItemNeed, HybridUserNeed
from flask_presst.principal.permission import HybridPermission


PERMISSION_DEFAULTS = {
    'read': 'yes',
    'create': 'no',
    'update': 'create',
    'delete': 'update'
}

DEFAULT_METHODS = ('read', 'create', 'update', 'delete')


class PrincipalResourceMeta(ModelResourceMeta):
    def __new__(mcs, name, bases, members):
        class_ = super(PrincipalResourceMeta, mcs).__new__(mcs, name, bases, members)
        meta = class_._meta

        if meta:
            class_._raw_needs = needs = getattr(class_, '_raw_needs', PERMISSION_DEFAULTS).copy()
            needs.update(meta.get('permissions', {}))

        return class_


class PrincipalResource(six.with_metaclass(PrincipalResourceMeta, ModelResource)):
    """
    :class:`PrincipalResource` parses the ``Meta.permissions`` attribute. Permission methods that are not specified are
    read from ``PERMISSION_DEFAULTS``.

    Internally, this resource uses a special type of :class:`flask_principal.Permission`:
    :class:`HybridPermission`. This permission class can evaluate :class:`HybridNeed` objects that can look up needs
    from `item` or `query` objects.

    It is necessary to handle authentication separately, e.g. using Flask-Login with appropriate decorators.
    """
    _raw_needs = PERMISSION_DEFAULTS

    @classproperty
    def _needs(cls):
        if hasattr(cls, '_needs_cache'):
            return cls._needs_cache

        needs_map = cls._raw_needs.copy()
        methods = needs_map.keys()

        def convert(method, needs, map, path=()):
            options = set()

            if isinstance(needs, six.string_types):
                needs = [needs]
            if isinstance(needs, set):
                return needs

            for need in needs:
                if need == 'no':
                    options.add(Permission(('permission-denied',)))
                elif need == 'yes':
                    return {True}
                elif need in methods:
                    if need == method:
                        options.add(HybridItemNeed(method, cls))
                    elif need in path:
                        raise RuntimeError('Circular permissions in {} (path: {})'.format(cls, path))
                    else:
                        path += (method, )
                        options |= convert(need, map[need], map, path)

                elif ':' in need:
                    role, value = need.split(':')
                    field = cls._fields[value]

                    # TODO implement this for ToMany as well as ToOne
                    if isinstance(field, ToOne):
                        resource = field.resource

                        if role == 'user':
                            options.add(HybridUserNeed(field))
                        elif role == 'role':
                            options.add(RoleNeed(value))
                        else:
                            for imported_need in resource._needs[role]:
                                if isinstance(imported_need, HybridItemNeed):
                                    imported_need = imported_need.extend(field)
                                options.add(imported_need)
                else:
                    options.add(RoleNeed(need))

            return options

        for method, needs in needs_map.items():
            converted_needs = convert(method, needs, needs_map)
            needs_map[method] = converted_needs

        cls._needs_cache = needs_map
        return needs_map

    @classproperty
    def _permissions(cls):
        # if cls in current_app.presst.permissions:
        #     return current_app.presst.permissions[cls]

        permissions = {}

        for method, needs in cls._needs.items():
            if True in needs:
                needs = set()
            permissions[method] = HybridPermission(*(needs))

        # current_app.presst.permissions[cls.resource_name] = permissions
        return permissions

    @classmethod
    def get_permissions_for_item(cls, item):
        """
        Returns a dictionary of evaluated permissions for an item.

        :param item:
        :return: Dictionary in the form ``{method: bool, ..}``
        """
        return {method: permission.can(item) for method, permission in cls._permissions.items()}

    @classmethod
    def can_create_item(cls, item):
        """
        Looks up permissions on whether an item may be created.

        :param item:
        """
        permission = cls._permissions['create']
        return permission.can(item)

    @classmethod
    def can_update_item(cls, item, changes=None):
        """
        Looks up permissions on whether an item may be updated.

        :param item:
        :param changes: dictionary of changes
        """
        permission = cls._permissions['update']
        return permission.can(item)

    @classmethod
    def can_delete_item(cls, item):
        """
        Looks up permissions on whether an item may be deleted.

        :param item:
        """
        permission = cls._permissions['delete']
        return permission.can(item)

    @classmethod
    def get_item_list(cls):
        """
        Applies permissions to query and returns query.

        :raises HTTPException: If read access is entirely forbidden.
        """
        query = super(PrincipalResource, cls).get_item_list()

        read_permission = cls._permissions['read']
        query = read_permission.apply_filters(query)

        if query is None:
            # abort with 403, but only if permissions for this resource are role-based.
            if all(map(lambda p: p.method=='role', read_permission.needs)):
                abort(403, message='Permission denied: not allowed to access this resource')
            else:
                return []
        if isinstance(query, list):
            abort(500, message='Nesting not supported for this resource.')

        return query

    @classmethod
    def create_item(cls, properties, commit=True):
        if not cls.can_create_item(properties):
            abort(403)

        return super(PrincipalResource, cls).create_item(properties, commit)

    @classmethod
    def update_item(cls, item, changes, *args, **kwargs):
        if not cls.can_update_item(item, changes):
            abort(403)

        return super(PrincipalResource, cls).update_item(item, changes, *args, **kwargs)

    @classmethod
    def delete_item(cls, item):
        if not cls.can_delete_item(item):
            abort(403)

        return super(PrincipalResource, cls).delete_item(item)

    @classmethod
    def get_relationship(cls, item, relationship):
        query = super(PrincipalResource, cls).get_relationship(item, relationship)
        child_resource = cls.routes[relationship].resource

        if issubclass(child_resource, PrincipalResource):
            read_permission = child_resource._permissions['read']
            query = read_permission.apply_filters(query)

        # TODO abort with 403, but only if permissions for this resource are role-based.
        if query is None:
            return []
        return query

    # @classmethod
    # def add_to_relationship(cls, item, relationship, child):
    #     child_resource = cls.routes[relationship].resource
    #
    #     if not cls.can_update_item(item) or child_resource.can_update_item(child):
    #         abort(403)
    #
    #     return super(PrincipalResource, cls).add_to_relationship(item, relationship, child)
    #
    # @classmethod
    # def remove_from_relationship(cls, item, relationship, child):
    #     child_resource = cls.routes[relationship].resource
    #
    #     if not cls.can_update_item(item) or child_resource.can_update_item(child):
    #         abort(403)
    #
    #     return super(PrincipalResource, cls).remove_from_relationship(item, relationship, child)
