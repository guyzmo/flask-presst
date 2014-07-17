from importlib import import_module
import inspect

from flask_restful import Api, abort
import six
from werkzeug.utils import cached_property

from flask_presst.schema import HyperSchema
from flask_presst.resources import PresstResource, ModelResource
from flask_presst.utils.routes import route_from


class PresstApi(Api):
    """


    """

    def __init__(self, *args, **kwargs):
        self.pagination_max_per_page = None
        self.pagination_default_per_page = None
        super(PresstApi, self).__init__(*args, **kwargs)
        self._presst_resources = {}
        self._presst_resource_insts = {}
        self._model_resource_map = {}


    def _init_app(self, app):
        super(PresstApi, self)._init_app(app)
        app.presst = self

        self.pagination_max_per_page = app.config.get('PRESST_MAX_PER_PAGE', 100)
        self.pagination_default_per_page = app.config.get('PRESST_DEFAULT_PER_PAGE', 20)

        # Add Schema URL rule
        self.app.add_url_rule(self._complete_url('/schema', ''),
                      view_func=self.output(HyperSchema.as_view('schema', self)),
                      endpoint='schema',
                      methods=['GET'])

    def get_resource_class(self, reference, module_name=None):
        """

        Accepts a reference of a resource and returns the matching :class:`PresstResource`.

        References can be one of:

        - a :class:`PresstResource`
        - an endpoint name for the resource
        - the full class path of the resource (or class name if :attr:`module` is set)
        - the :class:`Model` class of a :class:`ModelResource`

        :param reference: The resource reference
        :param module_name: module name for lazy loading of class.
        :return: :class:`PresstResource`
        """
        if isinstance(reference, PresstResource):  # pragma: no cover
            return reference.__class__
        elif inspect.isclass(reference) and issubclass(reference, PresstResource):
            return reference
        elif reference in self._model_resource_map:
            return self._model_resource_map[reference]
        elif isinstance(reference, six.string_types):
            if reference.lower() in self._presst_resources:
                return self._presst_resources[reference.lower()]
            else:
                if '.' in reference:
                    module_name, class_name = reference.rsplit('.', 1)
                else:
                    class_name = reference
                if not module_name:
                    raise RuntimeError('Unable to resolve resource reference: "{}"'.format(reference))
                module = import_module(module_name)
                return getattr(module, class_name)  # TODO check if this is actually a `Resource`

    def parse_resource_uri(self, uri):
        if not uri.startswith(self.prefix):
            abort(400, message='Resource URI {} does not begin with API prefix'.format(uri))

        endpoint, args = route_from(uri)

        try:
            return self._presst_resources[endpoint], args['id']
        except KeyError:
            abort(400, message='Resource {} is not defined'.format(uri))

    def get_item_for_uri(self, uri, expected_resource=None):
        if not isinstance(uri, six.text_type):
            abort(400, message='Resource URI must be a string')

        resource_class, id_ = self.parse_resource_uri(uri)

        if expected_resource != resource_class:
            abort(400, message='Wrong resource item type, expected {0}, got {1}'.format(
                expected_resource.resource_name,
                resource_class.resource_name
            ))

        return resource_class.get_item_for_id(id_)

    def get_resource_for_model(self, model):
        try:
            return self._model_resource_map[model]
        except KeyError:
            return None

    @cached_property
    def schema(self):
        definitions = {
            '_pagination': {
                'type': 'object',
                'properties': {
                    'per_page': {
                        'type': 'integer',
                        'minimum': 1,
                        'maximum': self.pagination_max_per_page,
                        'default': self.pagination_default_per_page
                    },
                    'page': {
                        'type': 'integer',
                        'minimum': 1,
                        'default': 1
                    }
                }
            }
        }

        return {
            '$schema': 'http://json-schema.org/draft-04/hyper-schema#',
            'definitions': definitions,
            'properties': {
                resource.resource_name: {
                    '$ref': self._complete_url('{}/schema#'.format(resource.route_prefix), '')
                } for resource in self._presst_resources.values()
            }
        }

    def add_resource(self, resource, *urls, **kwargs):

        # fallback to Flask-RESTful `add_resource` implementation with regular resources:
        if not issubclass(resource, PresstResource):
            super(PresstApi, self).add_resource(resource, *urls, **kwargs)

        # skip resources that may have previously been (auto-)imported.
        if resource in self._presst_resources.values():
            return

        resource.api = self

        resource_name = resource.resource_name

        pk_converter = resource._meta.get('pk_converter', 'int')

        resource.route_prefix = '/{0}'.format(resource_name)

        urls = [
            resource.route_prefix,
            '{0}/<{1}:id>'.format(resource.route_prefix, pk_converter),
        ]

        self._presst_resources[resource_name] = resource

        if issubclass(resource, ModelResource):
            self._model_resource_map[resource.get_model()] = resource

        for name, child in six.iteritems(resource.routes):

            if child.collection:
                url = '/{0}/{1}'.format(resource_name, name)
            else:
                url = '/{0}/<{1}:parent_id>/{2}'.format(resource_name, pk_converter, name)

            child_endpoint = '{0}_{1}_{2}'.format(resource_name, name, child.__class__.__name__.lower())
            child_view_func = self.output(child.view_factory(child_endpoint, resource))

            # FIXME routing for blueprints; also needs tests
            rule = self._complete_url(url, '')

            self.app.add_url_rule(rule,
                                  view_func=child_view_func,
                                  endpoint=child_endpoint,
                                  methods=child.methods, **kwargs)

        super(PresstApi, self).add_resource(resource, *urls, endpoint=resource_name, **kwargs)


