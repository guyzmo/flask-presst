import unittest
from flask_presst import fields, Relationship, resource_method
from tests import TestPresstResource, PresstTestCase


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

        with self.app.test_client() as client:
            self.assertEqual(self.parse_response(client.get('/apple')),
                             ([{"name": "A1", "resource_uri": "/apple/1"}], 200))

            self.assertEqual(self.parse_response(client.get('/apple/1/seeds')),
                             ([{"name": "S1", "resource_uri": "/seed/1"},
                               {"name": "S2", "resource_uri": "/seed/2"}],
                              200))


if __name__ == '__main__':
    unittest.main()
