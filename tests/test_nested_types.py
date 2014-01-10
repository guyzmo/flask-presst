import unittest
from flask.ext.presst import fields, Relationship, resource_method
from tests import TestPresstResource, PresstTestCase


class TestRelationship(PresstTestCase):
    def setUp(self):
        super(TestRelationship, self).setUp()

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

        self.Apple = Apple
        self.api.add_resource(Apple)
        self.api.add_resource(Seed)

    def test_get(self):
        self.assertEqual(self.Apple.seeds.relationship_name, 'seeds')

        self.request('GET', '/apple', None, [{"name": "A1", "resource_uri": "/apple/1"}], 200)
        self.request('GET', '/apple/1/seeds', None, [
            {"name": "S1", "resource_uri": "/seed/1"},
            {"name": "S2", "resource_uri": "/seed/2"}], 200)

    def test_patch_not_allowed(self):
        self.request('PATCH', '/apple/1/seeds', None, None, 405)
        self.request('PATCH', '/apple/1/seeds/1', {}, None, 404)  # NOTE may change to 405.

    @unittest.skip("POST to Relationship not yet implemented")
    def test_post(self):
        self.request('POST', '/apple/1/seeds/3', None, {"name": "S3", "resource_uri": "/seed/3"}, 200)
        self.request('GET', '/apple/seed_count', None, 3, 200)

    @unittest.skip("DELETE from Relationship not yet implemented")
    def test_delete(self):
        self.test_post()
        self.request('DELETE', '/apple/1/seeds/3', None, None, 204)
        self.request('GET', '/apple/seed_count', None, 2, 200)


class TestRelationshipField(PresstTestCase):
    def test_self(self):
        class Node(TestPresstResource):
            items = []
            parent = fields.ToOne('self')

        self.assertEqual(Node.parent.resource_class, Node)

    def node_resource_factory(self, embedded=False):
        class Node(TestPresstResource):
            items = []

            name = fields.String()
            parent = fields.ToOne('self', embedded=embedded)

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
                     {'name': 'child', 'parent': '/node/2', 'resource_uri': '/node/1'}, 200)
        self.request('GET', '/node/3', None,
                     {'name': 'grandparent', 'parent': None, 'resource_uri': '/node/3'}, 200)

    def test_update(self):
        Node = self.node_resource_factory(embedded=False)
        self.api.add_resource(Node)

        self.request('PATCH', '/node/1', {'parent': '/node/3'},
                     {'name': 'child', 'parent': '/node/3', 'resource_uri': '/node/1'}, 200)

        self.request('PATCH', '/node/1', {'parent': None},
                     {'name': 'child', 'parent': None, 'resource_uri': '/node/1'}, 200)

    def test_embedded(self):
        # NOTE: circular embedding is bad practice. do not do this.
        Node = self.node_resource_factory(embedded=True)

        self.api.add_resource(Node)
        self.request('GET', '/node/1', None,
                     {'name': 'child',
                      'parent': {'name': 'parent',
                                 'parent': {'name': 'grandparent',
                                            'parent': None,
                                            'resource_uri': '/node/3'},
                                 'resource_uri': '/node/2'},
                      'resource_uri': '/node/1'}, 200)

    def test_many(self):
        class Seed(TestPresstResource):
            items = [{'id': i, 'name': 'seed-{}'.format(i)} for i in range(1, 7)]
            name = fields.String()

        class Apple(TestPresstResource):
            seeds = fields.ToMany(Seed, embedded=True)

        for a in range(1, 4):
            Apple.items.append({'id': a, 'seeds': [Seed.get_item_for_id(i) for i in (a, a + 3)]})

        class Tree(TestPresstResource):
            items = [{'id': 1, 'apples': list(Apple.items)}]
            name = fields.String()
            apples = fields.ToMany(Apple)

        for resource in (Seed, Apple, Tree):
            self.api.add_resource(resource)

        self.request('GET', '/tree/1', None,
                     {'apples': ['/apple/1', '/apple/2', '/apple/3'],
                      'name': None,
                      'resource_uri': '/tree/1'}, 200)

        self.request('GET', '/apple/1', None,
                     {'seeds': [
                         {'name': 'seed-1', 'resource_uri': '/seed/1'},
                         {'name': 'seed-4', 'resource_uri': '/seed/4'}],
                      'resource_uri': '/apple/1'}, 200)

        self.request('PATCH', '/tree/1', {'apples': ['/apple/1', '/apple/2']},
                     {'apples': ['/apple/1', '/apple/2'],
                      'name': None,
                      'resource_uri': '/tree/1'}, 200)

        self.request('GET', '/apple/3', None,
                     {'seeds': [
                         {'name': 'seed-3', 'resource_uri': '/seed/3'},
                         {'name': 'seed-6', 'resource_uri': '/seed/6'}],
                      'resource_uri': '/apple/3'}, 200)

        self.request('PATCH', '/apple/3', {'seeds': ['/seed/3']},
                     {'seeds': [{'name': 'seed-3', 'resource_uri': '/seed/3'}],
                      'resource_uri': '/apple/3'}, 200)

        self.request('PATCH', '/apple/3', {'seeds': []},
                     {'seeds': [],
                      'resource_uri': '/apple/3'}, 200)

        self.request('PATCH', '/apple/3', {'seeds': ['/seed/1']},
                     {'seeds': [{'name': 'seed-1', 'resource_uri': '/seed/1'}],
                      'resource_uri': '/apple/3'}, 200)


if __name__ == '__main__':
    unittest.main()
