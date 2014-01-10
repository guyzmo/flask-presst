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

    def test_embedded(self):
        pass


if __name__ == '__main__':
    unittest.main()
