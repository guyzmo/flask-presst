from flask.ext.restful import abort


class Processor(object):
    """
    The `Processor` class has two types of methods that can be implemented.

    - *filters_before**. These are applied to an `SQLAlchemy` query.
    - *before_**. These are applied to an `SQLAlchemy` object after it has been initialized, but before the changes
    are committed.
    """

    def filter(self, method, query, resource_class):
        if method in ('HEAD', 'GET'):
            return self.filter_before_read(query, resource_class)
        elif method in ('POST', 'PATCH'):
            return self.filter_before_read(query, resource_class)
        elif method in ('DELETE',):
            return self.filter_before_delete(query, resource_class)
        else:
            return query

    def filter_before_read(self, query, resource_class):
        return query

    def filter_before_update(self, query, resource_class):
        return query

    def filter_before_delete(self, query, resource_class):
        return query

    def before_create_item(self, item, resource_class):
        """When used with :class:`ModelResource`, this method is called before the commit."""
        pass

    def before_update_item(self, object_, changes, is_partial, resource_class):
        pass

    def before_delete_item(self, item, resource_class):
        pass


class ModelAuthorization(Processor):
    """
    An authorization class for SQLAlchemy models and Flask-Login.

    Resource models need to implement a method :meth:`has_permission(user, permission)` decorated with the SQLAlchemy
    `hybrid_method` decorator.

    The following permissions need to be supported: `'create'`, `'read'`, `'update'`, `'delete'`. The `'create'`
    permission needs to be accessible before the object has been created in the database.
    """

    def get_current_user(self):
        raise NotImplementedError()

    def filter_before_read(self, query, resource_class):
        return query.filter(resource_class.get_model().has_permission(self.get_current_user(), 'read'))

    def filter_before_update(self, query, resource_class):
        return query.filter(resource_class.get_model().has_permission(self.get_current_user(), 'update'))

    def filter_before_delete(self, query, resource_class):
        return query.filter(resource_class.get_model().has_permission(self.get_current_user(), 'delete'))

    def before_create_item(self, item, resource_class):
        """
        The method fails with the *403 Forbidden* status code. If the *POST* method is not supported *at all*,
        this rule should be implemented using :func:`restrict_methods`.
        """
        if not item.has_permission(self.get_current_user(), 'create'):
            abort(403)

