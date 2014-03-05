class Processor(object):
    """
    The `Processor` class has two types of methods that can be implemented.

    - *filters_before**. These are applied to an `SQLAlchemy` query.
    - *before_**. These are applied to an `SQLAlchemy` object after it has been initialized, but before the changes
    are committed.
    """

    def filter(self, query, method, resource_class):
        if method in ('HEAD', 'GET'):
            return self.filter_before_read(query, resource_class)
        elif method in ('POST', 'PATCH'):
            return self.filter_before_update(query, resource_class)
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

    def after_create_item(self, item, resource_class):
        pass

    def before_update_item(self, item, changes, is_partial, resource_class):
        pass

    def after_update_item(self, item, resource_class):
        pass

    def before_delete_item(self, item, resource_class):
        pass

    def after_delete_item(self, item, resource_class):
        pass

    def before_create_relationship(self, item, relationship, relationship_item, resource_class):
        pass

    def after_create_relationship(self, item, relationship, relationship_item, resource_class):
        pass

    def before_delete_relationship(self, item, relationship, relationship_item, resource_class):
        pass

    def after_delete_relationship(self, item, relationship, relationship_item, resource_class):
        pass


class ProcessorSet(set):

    def filter(self, query, *args, **kwargs):
        for processor in self:
            query = processor.filter(query, *args, **kwargs)
        return query

    def __getattr__(self, item):
        def _process(*args, **kwargs):
            for processor in self:
                getattr(processor, item)(*args, **kwargs)

        return _process