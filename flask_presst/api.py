from importlib import import_module
import inspect
from flask.ext.restful import Api, abort, Resource
from flask.ext.presst.resources import PresstResource, ModelResource
from flask.ext.presst.utils.routes import route_from


class PresstApi(Api):

    def __init__(self, *args, **kwargs):
        super(PresstApi, self).__init__(*args, **kwargs)
        self._presst_resources = {}
        self._presst_resource_insts = {}
        self._model_resource_map = {}

    def get_resource_class(self, resource, module_name=None):
        """

        Accepts a reference of a resource and returns the matching :class:`PrestoResource`.

        References can be one of:

        - a :class:`PrestoResource`
        - an endpoint name for the resource
        - the full class path of the resource (or class name if :attr:`module` is set)
        - the :class:`Model` class of a :class:`ModelResource`

        :param resource: The resource reference
        :param module_name: module name for lazy loading of class.
        :returns: :class:`PrestoResource`
        """
        if isinstance(resource, PresstResource):
            return resource
        elif inspect.isclass(resource) and issubclass(resource, PresstResource):
            return resource
        elif resource in self._model_resource_map:
            return self._model_resource_map[resource]
        else:
            if not module_name or ('.' in resource):
                module_name, class_name = resource.rsplit('.', 1)
            else:
                class_name = resource
            module = import_module(module_name)
            # TODO check if this is actually a `Resource`
            return getattr(module, class_name)

    def get_instance(self, resource):
        return

    def parse_resource_uri(self, uri, method='GET'):
        if not uri.startswith(self.prefix):
            abort(400, message='Resource URI {} does not begin with API prefix'.format(uri))

        endpoint, args = route_from(uri)

        try:
            return self._presst_resources[endpoint], args['id']
        except KeyError:
            abort(400, message='Resource {} is not defined'.format(uri))

    def get_item_for_resource_uri(self, uri, expected_resource=None):
        resource_class, id = self.parse_resource_uri(uri)

        if expected_resource != resource_class:
            abort(400, message='Wrong resource item type, expected {1}, got {0}'.format(
                expected_resource.resource_name,
                resource_class.resource_name
            ))

        return resource_class.get_item_for_id(id)

    # TODO

    def add_resource(self, resource, pk_converter='int', *urls, **kwargs):

        # fallback to Flask-RESTful `add_resource` implementation with regular resources:
        if not issubclass(resource, PresstResource):
            super(PresstApi, self).add_resource(resource, *urls, **kwargs)


        # TODO overload regular add_resource method

        # Skip resources that may have previously been (auto-)imported.
        if resource in self._presst_resources:
            return

        resource_name = resource.resource_name.lower()

        resource.api = self

        # NOTE hack to run caching methods in __init__()
        # resource.init_api(self, namespace=namespace)

        # Process any string references to resources in ToOneField and ToManyField:
        # for field in resource._fields.values():
        #     if isinstance(field, ResourceFieldBase):
        #         if isinstance(field.resource_class, basestring):
        #             if field.resource_class == 'self':
        #                 field.resource_class = resource
        #             elif field.resource_class in self._model_resource_map:
        #                 field.resource_class = self._model_resource_map[field.resource_class]
        #             else: # TODO wait with resolving these until all resources have been added.
        #                 field.resource_class = self.get_resource_class(field.resource_class, resource.__module__)
        #

            # Create any nested collections as required (these may only support GET and perhaps POST and DELETE):

            # If embedded=False, subsequently remove from list of fields.

        urls = [
            '/{0}'.format(resource_name),
            '/{0}/<{1}:id>'.format(resource_name, pk_converter),
            '/{0}/<{1}:id>/<string:route>'.format(resource_name, pk_converter),
            '/{0}/<string:route>'.format(resource_name)
            # FIXME does not allow for collection-wide resource methods in resources with string keys.
        ]

        print 'XXX', resource.nested_types

        self._presst_resources[resource_name] = resource

        if issubclass(resource, ModelResource):
            self._model_resource_map[resource.get_model()] = resource

        for route, nested_type in resource.nested_types.iteritems():


            #print nested_resource, route
            #print '/{0}/<{1}:parent_id>/{2}'.format(resource_name, pk_converter, route)

            for relationship, method in nested_type.bound_resource.nested_types.iteritems():
                if not method.collection:  # 2-level nesting is only supported for collection methods.
                    continue

                print '/{0}/<{1}:parent_id>/{2}/{3}'.format(resource_name, pk_converter, route, relationship)

            # TODO get all (nested collections) and collection resource methods from resource.
            # TODO deal with recursive nested resources


            # if nested_type.collection:
            #     raise NotImplementedError()
            # else:
            #     print  '/{0}/<{1}:parent_id>/{2}'.format(resource_name, pk_converter, route)
                # print 'methods:', nested_type.methods
                # super(PresstApi, self).add_resource(
                #     nested_type,
                #     '/{0}/<{1}:parent_id>/{2}'.format(resource_name, pk_converter, route),
                #     endpoint='{0}_{1}'.format(resource_name, route))


            #
            #print (nested_resource, nested_resource_uri)
            #
            #super(ModelApi, self).add_resource(nested_resource, nested_resource_uri)

        # Add resource with provided URL and args:

        print urls

        super(PresstApi, self).add_resource(resource, *urls, endpoint=resource_name, **kwargs)


