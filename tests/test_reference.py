from flask_presst import fields, ResourceRef
from tests import PresstTestCase, SimpleResource


class TestResourceRef(PresstTestCase):
    class Fruit(SimpleResource):
        items = [{'id': 1, 'name': 'Banana'}]

        name = fields.String()

        class Meta:
            resource_name = 'fruit'

    class Vegetable(SimpleResource):
        items = [{'id': 1, 'name': 'Carrot'}]

    def setUp(self):
        super(TestResourceRef, self).setUp()
        self.api.add_resource(self.Fruit)
        self.api.add_resource(self.Vegetable)

    def test_reference_resolve(self):
        self.assertEqual(ResourceRef('{}.Vegetable'.format(self.__module__)).resolve(), self.Vegetable)
        self.assertEqual(ResourceRef('Fruit').resolve(), self.Fruit)
        self.assertEqual(ResourceRef(self.Fruit).resolve(), self.Fruit)

    def test_reference_repr(self):
        self.assertEqual(repr(ResourceRef(self.Fruit)), "<ResourceRef 'fruit'>")

    def test_reference_resolve_error(self):
        with self.assertRaises(RuntimeError):
            ResourceRef('Grain').resolve()
        with self.assertRaises(RuntimeError):
            ResourceRef('Meat').resolve()


Vegetable = TestResourceRef.Vegetable