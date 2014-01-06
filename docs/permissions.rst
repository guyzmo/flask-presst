Permissions for :class:`ModelResource` resources can be implemented using a custom :class:`Processor`.

Example implementation of a `ModelAuthorization` processor::

    class ModelAuthorization(Processor):
        """
        An authorization class for SQLAlchemy models and Flask-Login.

        Resource models need to implement a method :meth:`has_permission(user, permission)` decorated with the SQLAlchemy
        `hybrid_method` decorator.

        The following permissions need to be supported: `'create'`, `'read'`, `'update'`, `'delete'`. The `'create'`
        permission needs to be accessible before the object has been created in the database.
        """

        def get_current_user(self):
            return current_user

        def filter_before_read(self, query, resource_class):
            return query.filter(resource_class.model.has_permission(self.get_current_user(), 'read'))

        def filter_before_update(self, query, resource_class):
            return query.filter(resource_class.model.has_permission(self.get_current_user(), 'update'))

        def filter_before_delete(self, query, resource_class):
            return query.filter(resource_class.model.has_permission(self.get_current_user(), 'delete'))

        def before_create_object(self, object_, resource_class):
            """
            The method fails with the *403 Forbidden* status code. If the *POST* method is not supported *at all*,
            this rule should be implemented using :func:`restrict_methods`.
            """
            if not object_.has_permission(self.get_current_user(), 'create'):
                abort(403)



In this example, each `model` class has requires a method :func:`has_permission(user_obj, permission)` with the
decorated with the `hybrid_method` decorator. Example implementation of `has_permission` for a model:::

    @hybrid_method
    def has_permission(self, user, permission='read'):
        return {
            'create': True,
            'read': _or(self.groups.any(Group.members.any(User.id == user.id)), self.owner_id == user.id),
            'update': self.owner_id == user.id,
            'delete': False
        }[permission]
