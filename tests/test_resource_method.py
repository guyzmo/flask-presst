import json
from flask.ext.presst import fields, resource_method, Reference
from tests import PresstTestCase, TestPresstResource


class TestResourceMethod(PresstTestCase):
    def setUp(self):
        super(TestResourceMethod, self).setUp()

        class Citrus(TestPresstResource):
            items = [{'id': 1, 'name': 'Orange', 'sweetness': 3},
                     {'id': 2, 'name': 'Lemon', 'sweetness': 1},
                     {'id': 3, 'name': 'Clementine', 'sweetness': 5}]

            name = fields.String()
            sweetness = fields.Integer()

            @resource_method('GET')
            def name_length(self, citrus, *args, **kwargs):
                return len(citrus['name'])

            @resource_method('GET', collection=True)
            def count(self, item_list):
                return len(item_list)

            @resource_method('GET')
            def sweeter_than(self, citrus, other):
                return citrus['sweetness'] > other['sweetness']

            @resource_method('POST')
            def sweeten(self, citrus, by):
                citrus['sweetness'] += by
                return self.marshal_item(citrus)

            sweeten.add_argument('by', location='args', type=int, required=True)

        Citrus.sweeter_than.add_argument('other', type=Reference(Citrus))

        self.Citrus = Citrus
        self.api.add_resource(Citrus)

    def test_item_method(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/citrus/1/name_length')), (6, 200))
            self.assertEqual(self.parse_response(client.get('/citrus/2/name_length')), (5, 200))

    def test_collection_method(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/citrus/count')), (3, 200))

    def test_arguments(self):
        # required & verification & defaults.
        pass

    def test_callable(self):
        with self.app.test_request_context('/citrus/1'):
            instance = self.Citrus()
            instance.sweeten(self.Citrus.get_item_for_id(1), 5)

            self.assertEqual({'id': 1, 'name': 'Orange', 'sweetness': 8}, self.Citrus.get_item_for_id(1))

    def test_convert_argument(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.post('/citrus/3/sweeten?by=2')),
                             ({"name": "Clementine", "resource_uri": "/citrus/3", "sweetness": 7}, 200))

    def test_required_argument(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.post('/citrus/1/sweeten')), (None, 400))

    def test_optional_argument(self):
        pass

    def test_reference_argument(self):
        with self.app.test_client() as client:
            for citrus_id, other_id, val in ((1, 2, True), (1, 3, False), (2, 1, False), (3, 2, True)):
                self.assertEqual(self.parse_response(client.get('/citrus/{}/sweeter_than'.format(citrus_id),
                                                                data=json.dumps(
                                                                    {'other': '/citrus/{}'.format(other_id)}),
                                                                content_type='application/json')), (val, 200))

    def test_2_level(self):
        pass