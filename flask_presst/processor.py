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


class ProcessorSet(set):

    def filter(self, query, *args, **kwargs):
        for processor in self:
            query = processor.filter(query, *args, **kwargs)
        return query
