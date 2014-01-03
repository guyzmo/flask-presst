import json
import unittest
from flask import Flask
from flask.ext.restful import abort
from werkzeug import exceptions
from flask_presst import fields, PresstResource, PresstApi, Relationship, resource_method, Reference


class TestPresstResource(PresstResource):
    items = []

    @classmethod
    def get_item_for_id(cls, id_):
        for item in cls.items:
            if item['id'] == id_:
                return item
        abort(404)

    @classmethod
    def get_item_list(cls):
        return cls.items

    @classmethod
    def get_item_list_for_relationship(cls, relationship, parent_item):
        return (cls.get_item_for_id(id) for id in parent_item[relationship])

    @classmethod
    def create_item_relationship(cls, id_, relationship, parent_item):
        raise NotImplementedError()

    @classmethod
    def delete_item_relationship(cls, id_, relationship, parent_item):
        raise NotImplementedError()

    @classmethod
    def create_item(cls, dct):
        """This method must either return the created item or abort with the appropriate error."""
        item_id = len(cls.items) + 1
        dct.update(item_id)
        cls.items[item_id] = dct
        return dct

    @classmethod
    def update_item(cls, id_, dct, is_partial=False):
        "This method must either return the updated item or abort with the appropriate error."
        item = cls.get_item_for_id(id_)
        item.update(dct)
        return dct

    @classmethod
    def delete_item(cls, id_):
        try:
            del cls.items[id_]
        except KeyError:
            abort(404)
        return None, 204


class PresstTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app = Flask(__name__)
        # self.db_fd, flaskr.app.config['DATABASE'] = tempfile.mkstemp()
        # flaskr.app.config['TESTING'] = True
        # flaskr.init_db()

        app.testing = True

        self.api = PresstApi(app)

    def tearDown(self):
        pass

    def parse_response(self, r):
        v = json.loads(r.get_data()) if r.status_code == 200 else None
        return v, r.status_code


class TestReference(PresstTestCase):

    class Fruit(TestPresstResource):
        items = [{'id': 1, 'name': 'Banana'}]

        name = fields.String()

    class Vegetable(TestPresstResource):
        items = [{'id': 1, 'name': 'Carrot'}]

    def setUp(self):
        super(TestReference, self).setUp()
        self.api.add_resource(self.Fruit)
        self.api.add_resource(self.Vegetable)

    def test_reference_resolve(self):
        pass

    def test_reference(self):
        reference = Reference(self.Fruit)
        with self.app.test_request_context('/'):
            self.assertEqual(reference('/fruit/1'), {'id': 1, 'name': 'Banana'})

    def test_reference_not_found(self):
        reference = Reference(self.Fruit)
        with self.app.test_request_context('/'):
            self.assertRaises(exceptions.NotFound, lambda: reference('/fruit/2'))

    def test_reference_wrong_resource(self):
        reference = Reference(self.Fruit)
        with self.app.test_request_context('/'):
            self.assertRaises(exceptions.BadRequest, lambda: reference('/vegetable/1'))


class TestNestedRelationship(PresstTestCase):
    def test_get(self):
        class Seed(TestPresstResource):
            items = [
                {'id': 1, 'name': 'S1'},
                {'id': 2, 'name': 'S2'},
                {'id': 3, 'name': 'S3'}
            ]

            name = fields.String()

        class Apple(TestPresstResource):
            items = [{'id': 1, 'seeds': [1, 2], 'name': 'A1'}]
            name = fields.String()
            seeds = Relationship(resource=Seed)

            @resource_method('GET')
            def seed_count(self, apple):
                return len(apple['seeds'])

        self.assertEqual(Apple.seeds.relationship_name, 'seeds')

        self.api.add_resource(Apple)
        self.api.add_resource(Seed)

        print Apple.seed_count

        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/apple')),
                             ([{"name": "A1", "resource_uri": "/apple/1"}], 200))

            self.assertEqual(self.parse_response(client.get('/apple/1/seeds')),
                             ([{"name": "S1", "resource_uri": "/seed/1"},
                               {"name": "S2", "resource_uri": "/seed/2"}],
                              200))


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
            def count(self):
                return len(self.get_item_list())

            @resource_method('GET')
            def sweeter_than(self, citrus, other):
                return citrus['sweetness'] > other['sweetness']

            @resource_method('POST')
            def sweeten(self, citrus, by):# citrus, by):
                citrus['sweetness'] += by
                return self.marshal_item(citrus)

            sweeten.add_argument('by', location='args', type=int, required=True)

        Citrus.sweeter_than.add_argument('other', type=Reference(Citrus), required=True)

        self.api.add_resource(Citrus)


    def test_item_method(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/citrus/1/name_length')), (6, 200))
            self.assertEqual(self.parse_response(client.get('/citrus/2/name_length')), (5, 200))

    def test_collection_method(self):
        with self.app.test_client() as client:
            print client.get('/citrus/count')
            self.assertEqual(self.parse_response(client.get('/citrus/count')), (3, 200))

    def test_arguments(self):
        # required & verification & defaults.
        pass

    def test_convert_argument(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.post('/citrus/3/sweeten?by=2')),
                             ({"name": "Clementine", "resource_uri": "/citrus/3", "sweetness": 7}, 200))

    def test_required_argument(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.post('/citrus/1/sweeten')), (None, 400))

    def test_reference_argument(self):
        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/citrus/2/sweeter_than',
                                                             data=json.dumps({'other': '/citrus/1'}),
                                                             content_type='application/json')), (False, 200))

    def test_2_level(self):
        pass


if __name__ == '__main__':
    unittest.main()
