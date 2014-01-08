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
