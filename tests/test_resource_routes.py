import unittest
from flask_restful import marshal_with
from flask_presst.routes import route
from flask_presst import fields, Relationship, action
from tests import SimpleResource, PresstTestCase
from datetime import datetime
from pytz import UTC


class TestRouteMethods(PresstTestCase):
    def setUp(self):
        super(TestRouteMethods, self).setUp()

        class Object(SimpleResource):
            items = []

            @route('GET')
            def simple(self):
                return 'foo'

            @route.GET
            def simple_alt(self):
                return 'bar'

            @route.POST(route='/foo')
            def single(self):
                return True

            @route.GET
            def multiple(self):
                return 'get'

            @multiple.POST
            def multiple(self):
                return 'post'

            @multiple.DELETE
            def multiple(self):
                return 'delete'

            @route('GET')
            def parse_simple_get(self, a, b):
                return a * b

            parse_simple_get.add_argument('a', fields.Integer(default=0))
            parse_simple_get.add_argument('b', fields.Integer(default=0))

            @route('POST')
            def parse_simple_post(self, a, b):
                return a + b

            parse_simple_post.add_argument('a', fields.Integer(default=0))
            parse_simple_post.add_argument('b', fields.Integer(default=0))

            def parse_combined(self):
                pass

            @route.GET(response_property=fields.Nested({
                'name': fields.String(),
                'createdAt': fields.DateTime()
            }))
            def marshalled(self):
                return {"name": "Foo", "createdAt": datetime(2014, 1, 10, 12, 18, tzinfo=UTC)}

            def marshalled_alt(self):
                return {"name": "Foo", "createdAt": datetime(2014, 1, 10, 12, 18, tzinfo=UTC)}

            marshalled_alt.__annotations__ = {
                'return': fields.Nested({
                    'name': fields.String(),
                    'createdAt': fields.DateTime()
                })
            }

            marshalled_alt = route.GET(marshalled_alt)

            @route.POST(route='/variable/<int:id>')
            def variable(self, id):
                return {'id': id}

        self.object = Object
        self.api.add_resource(Object)

    def test_simple(self):
        response = self.client.get('/object/simple')
        self.assert200(response)
        self.assertEqual('foo', response.json)

    def test_simple_alt(self):
        self.assertEqual(['GET'], self.object.simple_alt.methods)
        response = self.client.get('/object/simple-alt')
        self.assert200(response)
        self.assertEqual('bar', response.json)

    def test_single(self):
        response = self.client.post('/object/foo')
        self.assert200(response)
        self.assertEqual(True, response.json)

    def test_multiple(self):
        self.assertEqual({'GET', 'POST', 'DELETE'}, set(self.object.multiple.methods))

        response = self.client.get('/object/multiple')

        self.assert200(response)
        self.assertEqual('get', response.json)

        self.assertEqual('post', self.client.post('/object/multiple').json)
        self.assertEqual('delete', self.client.delete('/object/multiple').json)

    def test_parse_simple_get(self):
        response = self.client.get('/object/parse-simple-get?a=2&b=3')
        self.assert200(response)
        self.assertEqual(6, response.json)

    def test_parse_simple_post(self):
        response = self.client.post('/object/parse-simple-post', data={'a': 7, 'b': 3})
        self.assert200(response)
        self.assertEqual(10, response.json)

    def test_marshalled(self):
        response = self.client.get('/object/marshalled')
        self.assert200(response)
        self.assertEqual({'createdAt': '2014-01-10T12:18:00+00:00', 'name': 'Foo'}, response.json)

    def test_marshalled_alt(self):
        response = self.client.get('/object/marshalled-alt')
        self.assert200(response)
        self.assertEqual({'createdAt': '2014-01-10T12:18:00+00:00', 'name': 'Foo'}, response.json)

    def test_variable(self):
        response = self.client.post('/object/variable/123')
        self.assert200(response)
        self.assertEqual({'id': 123}, response.json)


class TestRelationship(PresstTestCase):
    def setUp(self):
        super(TestRelationship, self).setUp()

        class Seed(SimpleResource):
            items = [
                {'id': 1, 'name': 'S1'},
                {'id': 2, 'name': 'S2'},
                {'id': 3, 'name': 'S3'}
            ]

            name = fields.String()

        class Apple(SimpleResource):
            items = [{'id': 1, 'seeds': [1, 2], 'name': 'A1'}]
            name = fields.String()
            seeds = Relationship(resource=Seed)

            @action('GET')
            def seed_count(self, apple):
                return len(apple['seeds'])

            @action('GET')
            @marshal_with({'first': fields.ToOne('seed', embedded=True), 'id': fields.Integer()})
            def first_seed(self, apple):
                first_seed_id = apple['seeds'][0]
                return {'first': Seed.get_item_for_id(first_seed_id), 'id': first_seed_id}

        self.Apple = Apple
        self.api.add_resource(Apple)
        self.api.add_resource(Seed)

    def test_get(self):
        self.assertEqual(self.Apple.seeds.attribute, 'seeds')

        self.request('GET', '/apple', None, [{"name": "A1", "_uri": "/apple/1"}], 200)
        self.request('GET', '/apple/1/seeds', None, [
            {"name": "S1", "_uri": "/seed/1"},
            {"name": "S2", "_uri": "/seed/2"}], 200)

    def test_patch_not_allowed(self):
        self.request('PATCH', '/apple/1/seeds', None, None, 405)
        self.request('PATCH', '/apple/1/seeds/1', {}, None, 404)  # NOTE may change to 405.

    def test_post(self):
        self.request('GET', '/seed/3', None, {'name': 'S3', '_uri': '/seed/3'}, 200)
        self.request('POST', '/apple/1/seeds', '/seed/3', {"name": "S3", "_uri": "/seed/3"}, 200)
        self.request('GET', '/apple/1/seed-count', None, 3, 200)

    def test_delete(self):
        self.test_post()
        self.request('DELETE', '/apple/1/seeds', '/seed/2', None, 204)
        self.request('GET', '/apple/1/seed-count', None, 2, 200)

    def test_post_missing_item(self):
        self.request('POST', '/apple/1/seeds', None, None, 400)
        self.request('POST', '/apple/1/seeds', '/seed/5', None, 404)

    def test_post_item_wrong_resource(self):
        self.request('POST', '/apple/1/seeds', '/apple/1', None, 400)
        self.request('POST', '/apple/1/seeds', ['/apple/1'], None, 400)

    def test_marshal(self):
        self.request('GET', '/apple/1/first-seed', None,
                     {'first': {'name': 'S1', '_uri': '/seed/1'}, 'id': 1}, 200)


class TestRelationshipField(PresstTestCase):
    def test_self(self):
        class Node(SimpleResource):
            items = []
            parent = fields.ToOne('self')

        self.assertEqual(Node.parent.resource, Node)

    def node_resource_factory(self, embedded=False):
        class Node(SimpleResource):
            items = []

            name = fields.String()
            parent = fields.ToOne('self', embedded=embedded, nullable=True)

        last = None
        for i, name in enumerate(('grandparent', 'parent', 'child')):
            item = {'id': 3 - i, 'name': name, 'parent': last}
            Node.items.append(item)
            last = item

        return Node

    def test_not_embedded(self):
        Node = self.node_resource_factory(embedded=False)

        self.api.add_resource(Node)

        self.request('GET', '/node/1', None,
                     {'name': 'child', 'parent': '/node/2', '_uri': '/node/1'}, 200)
        self.request('GET', '/node/3', None,
                     {'name': 'grandparent', 'parent': None, '_uri': '/node/3'}, 200)

    def test_update(self):
        Node = self.node_resource_factory(embedded=False)
        self.api.add_resource(Node)

        self.request('PATCH', '/node/1', {'parent': '/node/3'},
                     {'name': 'child', 'parent': '/node/3', '_uri': '/node/1'}, 200)

        self.request('PATCH', '/node/1', {'parent': None},
                     {'name': 'child', 'parent': None, '_uri': '/node/1'}, 200)

    def test_embedded(self):
        # NOTE: circular embedding is bad practice. do not do this.
        Node = self.node_resource_factory(embedded=True)

        self.api.add_resource(Node)
        self.request('GET', '/node/1', None,
                     {'name': 'child',
                      'parent': {'name': 'parent',
                                 'parent': {'name': 'grandparent',
                                            'parent': None,
                                            '_uri': '/node/3'},
                                 '_uri': '/node/2'},
                      '_uri': '/node/1'}, 200)

    def test_many(self):
        class Seed(SimpleResource):
            items = [{'id': i, 'name': 'seed-{}'.format(i)} for i in range(1, 7)]
            name = fields.String()

        class Apple(SimpleResource):
            seeds = fields.ToMany(Seed, embedded=True)

        for a in range(1, 4):
            Apple.items.append({'id': a, 'seeds': [Seed.get_item_for_id(i) for i in (a, a + 3)]})

        class Tree(SimpleResource):
            items = [{'id': 1, 'apples': list(Apple.items)}]
            name = fields.String()
            apples = fields.ToMany(Apple)

        for resource in (Seed, Apple, Tree):
            self.api.add_resource(resource)

        self.request('GET', '/tree/1', None,
                     {'apples': ['/apple/1', '/apple/2', '/apple/3'],
                      'name': None,
                      '_uri': '/tree/1'}, 200)

        self.request('GET', '/apple/1', None,
                     {'seeds': [
                         {'name': 'seed-1', '_uri': '/seed/1'},
                         {'name': 'seed-4', '_uri': '/seed/4'}],
                      '_uri': '/apple/1'}, 200)

        self.request('PATCH', '/tree/1', {'apples': ['/apple/1', '/apple/2']},
                     {'apples': ['/apple/1', '/apple/2'],
                      'name': None,
                      '_uri': '/tree/1'}, 200)

        self.request('GET', '/apple/3', None,
                     {'seeds': [
                         {'name': 'seed-3', '_uri': '/seed/3'},
                         {'name': 'seed-6', '_uri': '/seed/6'}],
                      '_uri': '/apple/3'}, 200)

        self.request('PATCH', '/apple/3', {'seeds': ['/seed/3']},
                     {'seeds': [{'name': 'seed-3', '_uri': '/seed/3'}],
                      '_uri': '/apple/3'}, 200)

        self.request('PATCH', '/apple/3', {'seeds': []},
                     {'seeds': [],
                      '_uri': '/apple/3'}, 200)

        self.request('PATCH', '/apple/3', {'seeds': ['/seed/1']},
                     {'seeds': [{'name': 'seed-1', '_uri': '/seed/1'}],
                      '_uri': '/apple/3'}, 200)


if __name__ == '__main__':
    unittest.main()
