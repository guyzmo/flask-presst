from importlib import import_module
import inspect
import six

class Reference(object):
    def __init__(self, reference):
        self._resource_class = self._resolve_resource_class(reference)

    def __call__(self, resource_uri):
        if resource_uri is None:
            return None
        return self._resource_class.api.get_item_for_resource_uri(resource_uri, self._resource_class)

    def __repr__(self):
        return "<Reference '{}'>".format(self._resource_class.__name__)

    @staticmethod
    def _resolve_resource_class(reference):
        from flask.ext.presst import PresstResource
        if inspect.isclass(reference) and issubclass(reference, PresstResource):
            return reference

        if isinstance(reference, six.string_types):
            module_name, class_name = reference.rsplit('.', 1)
            module = import_module(module_name)
            return getattr(module, class_name)
        else:
            raise RuntimeError('Could not resolve API resource reference: {}'.format(reference))

