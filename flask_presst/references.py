from collections import namedtuple
from importlib import import_module
import inspect
from flask.ext.restful import Resource
import six


ItemWrapper = namedtuple('ItemWrapper', ('resource', 'id', 'item', 'request_data'))



class ItemDocument(object):

    def __init__(self, resource, id=None, data=None):
        self.id = id
        self.data = data
        self.changes = None

    def update(self, properties, allow_partial=False):
        pass # TODO check properties against schema,


class Reference(object):
    def __init__(self, reference, api=None):
        self.resource_class = api.get_resource_class(reference) if api else self._resolve_resource_class(reference)
        self.resource = self.resource_class

    def __call__(self, value):
        if value is None:
            return None

        resource_uri = None
        request_data = None

        if isinstance(value, six.text_type):
            resource_uri = value
        elif isinstance(value, dict):
            if 'resource_uri' in value:
                request_data = dict(value)
                resource_uri = request_data.pop('resource_uri')
            else:
                request_data = value

        if resource_uri:
            resource, id = self.resource.api.parse_resource_uri(value)

            if self.resource != resource:
                raise ValueError('Wrong resource item type, expected {0}, got {1}'.format(
                    self.resource.resource_name,
                    resource.resource_name))

            return self.resource.request_make_item(id, data=request_data)
        else:
            return self.resource.request_make_item(data=request_data)

    def __repr__(self):
        return "<Reference '{}'>".format(self.resource_class.resource_name)

    @staticmethod
    def _resolve_resource_class(reference):
        from flask_presst import PresstResource

        if inspect.isclass(reference) and issubclass(reference, PresstResource):
            return reference

        try:
            if isinstance(reference, six.string_types):
                module_name, class_name = reference.rsplit('.', 1)
                module = import_module(module_name)
                return getattr(module, class_name)
        except ValueError:
            pass

        raise RuntimeError('Could not resolve API resource reference: {}'.format(reference))


class ResourceRef(object):
    def __init__(self, reference):
        self.reference_str = reference

    def __call__(self):
        return self.resolve()

    def resolve(self):
        """
        Resolve attempts three different methods for resolving a reference:

        - if the reference is a Resource, return it
        - if the reference is a Resource name in the current_app.unrest API context, return it
        - if the reference is a complete module.class string, import and return it
        """
        r = self.reference_str

        if inspect.isclass(r) and issubclass(r, Resource):
            return r

        try:
            if isinstance(r, six.string_types):
                module_name, class_name = r.rsplit('.', 1)
                module = import_module(module_name)
                return getattr(module, class_name)
        except ValueError:
            pass

        raise RuntimeError('Could not resolve resource reference: {}'.format(r))


#

