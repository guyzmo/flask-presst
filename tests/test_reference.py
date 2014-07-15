from werkzeug import exceptions
from werkzeug.exceptions import HTTPException
from flask.ext.presst import fields, Reference
from flask.ext.presst.references import ItemWrapper
from tests import PresstTestCase, SimpleResource


class TestReference(PresstTestCase):
    class Fruit(SimpleResource):
        items = [{'id': 1, 'name': 'Banana'}]

        name = fields.String()

        class Meta:
            resource_name = 'fruit'

    class Vegetable(SimpleResource):
        items = [{'id': 1, 'name': 'Carrot'}]

    def setUp(self):
        super(TestReference, self).setUp()
        self.api.add_resource(self.Fruit)
        self.api.add_resource(self.Vegetable)

    def test_reference_resolve(self):
        self.assertEqual(Reference('{}.Vegetable'.format(self.__module__)).resource_class, self.Vegetable)
        self.assertEqual(Reference('Fruit', api=self.api).resource_class, self.Fruit)
        self.assertEqual(repr(Reference(self.Fruit)), "<Reference 'fruit'>")

    def test_reference_resolve_error(self):
        with self.assertRaises(RuntimeError):
            Reference('Fruit')  # missing module name & no api key given.
        with self.assertRaises(RuntimeError):
            Reference('House')

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
            self.assertRaises(HTTPException, lambda: reference('/vegetable/1'))


Vegetable = TestReference.Vegetable