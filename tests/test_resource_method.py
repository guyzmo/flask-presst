from flask_presst import fields, action
from tests import PresstTestCase, SimpleResource
from flask_presst.routes import route, CollectionView

class TestResourceMethod(PresstTestCase):
    def setUp(self):
        super(TestResourceMethod, self).setUp()

        class Citrus(SimpleResource):
            items = [{'id': 1, 'name': 'Orange', 'sweetness': 3},
                     {'id': 2, 'name': 'Lemon', 'sweetness': 1},
                     {'id': 3, 'name': 'Clementine', 'sweetness': 5}]

            name = fields.String()
            sweetness = fields.Integer()

            @action('GET')
            def name_length(self, citrus):
                return len(citrus['name'])

            @action('GET', collection=True)
            def count(self, item_list):
                return len(item_list)

            @action('GET')
            def sweeter_than(self, citrus, other):
                # FIXME do not use Reference for these things
                return citrus['sweetness'] > other['sweetness']

            sweeter_than.add_argument('other', fields.ToOne('Citrus', nullable=False))

            @action('POST', response_property=fields.One('Citrus', nullable=False))
            def sweeten(self, citrus, by):
                citrus['sweetness'] += by
                return citrus

            sweeten.add_argument('by', fields.PositiveInteger(nullable=False))

            # TODO unit tests for Python 3 functionality:
            #
            # @action('POST')
            # def sweeten(self, citrus, by: fields.PositiveInteger()) -> fields.ToOne('Citrus'):
            #     citrus['sweetness'] += by
            #     return self.marshal_item(citrus)


        self.Citrus = Citrus
        self.api.add_resource(Citrus)

    def test_item_method(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/citrus/1/name-length')), (6, 200))
            self.assertEqual(self.parse_response(client.get('/citrus/2/name-length')), (5, 200))

    def test_collection_method(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/citrus/count')), (3, 200))

    def test_callable(self):
        with self.app.test_request_context('/citrus/1'):
            instance = self.Citrus()
            instance.sweeten(self.Citrus.get_item_for_id(1), 5)

            self.assertEqual({'id': 1, 'name': 'Orange', 'sweetness': 8}, self.Citrus.get_item_for_id(1))

    def test_convert_argument(self):
        response = self.client.post('/citrus/3/sweeten', data={'by': 2})
        self.assertEqual({"name": "Clementine", "_uri": "/citrus/3", "sweetness": 7}, response.json)

    def test_required_argument(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.post('/citrus/1/sweeten')), (None, 400))

    def test_optional_argument(self):
        pass

    def test_reference_argument(self):
        with self.app.test_client() as client:
            for citrus_id, other_id, val in ((1, 2, True), (1, 3, False), (2, 1, False), (3, 2, True)):
                response = client.get('/citrus/{}/sweeter-than?other=/citrus/{}'.format(citrus_id, other_id))
                self.assertEqual(response.json, val)

    def test_get_schema(self):
        response = self.client.get('/citrus/schema')

        self.maxDiff = None
        self.assertEqual({
                             'type': 'object',
                             'properties': {
                                 'name': {
                                     '$ref': '#/definitions/name'
                                 },
                                 '_uri': {
                                     '$ref': '#/definitions/_uri'
                                 },
                                 'sweetness': {
                                     '$ref': '#/definitions/sweetness'
                                 }
                             },
                             'definitions': {
                                 'name': {
                                     'type': ['string', 'null']
                                 },
                                 '_uri': {
                                     'type': 'string',
                                     'format': 'uri',
                                     'readOnly': True
                                 },
                                 'sweetness': {
                                     'type': ['integer', 'null']
                                 }
                             },
                             'required': [],
                             'links': [{
                                           'href': '/citrus/{id}',
                                           'rel': 'self',
                                           'method': 'GET'
                                       }, {
                                           'schema': {
                                               '$ref': '/schema#/definitions/_pagination'
                                           },
                                           'href': '/citrus',
                                           'rel': 'instances',
                                           'method': 'GET'
                                       }, {
                                           'href': '/citrus/count',
                                           'schema': {
                                               'type': 'object',
                                               'properties': {}
                                           },
                                           'rel': 'count',
                                           'method': 'GET',
                                           'targetSchema': {}
                                       }, {
                                           'href': '/citrus/{id}/name-length',
                                           'schema': {
                                               'type': 'object',
                                               'properties': {}
                                           },
                                           'targetSchema': {},
                                           'rel': 'name_length',
                                           'method': 'GET'
                                       }, {
                                           'href': '/citrus/{id}/sweeten',
                                           'schema': {
                                               'type': 'object',
                                               'properties': {
                                                   'by': {
                                                       'type': 'integer',
                                                       'minimum': 0
                                                   }
                                               },
                                               'required': ['by']
                                           },
                                           'targetSchema': {
                                               '$ref': '/citrus/schema#'
                                           },
                                           'rel': 'sweeten',
                                           'method': 'POST'
                                       }, {
                                           'href': '/citrus/{id}/sweeter-than',
                                           'schema': {
                                               'type': 'object',
                                               'properties': {
                                                   'other': {
                                                       'oneOf': [{
                                                                     '$ref': '/citrus/schema#/definitions/_uri'
                                                                 }, {
                                                                     '$ref': '/citrus/schema#'
                                                                 }]
                                                   }
                                               },
                                               'required': ['other']
                                           },
                                           'targetSchema': {},
                                           'rel': 'sweeter_than',
                                           'method': 'GET'
                                       }]
                         }, response.json)