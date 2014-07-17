from flask_sqlalchemy import SQLAlchemy
from flask_presst import fields, ModelResource
from tests import PresstTestCase, SimpleResource


class VegetableResource(SimpleResource):
    name = fields.String()

    class Meta:
        resource_name = 'vegetable'


class TestAPI(PresstTestCase):
    def setUp(self):
        super(TestAPI, self).setUp()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True

        self.db = db = SQLAlchemy(app)

        class Fruit(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

        class FruitResource(ModelResource):
            class Meta:
                model = Fruit

        class Pet(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

        db.create_all()

        self.Fruit = Fruit
        self.Pet = Pet
        self.FruitResource = FruitResource
        self.VegetableResource = VegetableResource

        self.api.add_resource(VegetableResource)
        self.api.add_resource(FruitResource)

    def test_get_resource_class(self):
        self.assertEqual(self.api.get_resource_class(self.FruitResource), self.FruitResource)
        self.assertEqual(self.api.get_resource_class('Fruit'), self.FruitResource)
        self.assertEqual(self.api.get_resource_class('vegetable'), self.VegetableResource)
        self.assertEqual(self.api.get_resource_class(self.Fruit), self.FruitResource)
        self.assertEqual(self.api.get_resource_class('{}.VegetableResource'.format(self.__module__)),
                         self.VegetableResource)
        self.assertEqual(self.api.get_resource_class('VegetableResource', module_name=self.__module__),
                         self.VegetableResource)

    def test_get_resource_for_model(self):
        self.assertEqual(self.api.get_resource_for_model(self.Fruit), self.FruitResource)
        self.assertEqual(self.api.get_resource_for_model(self.Pet), None)

    def test_get_schema(self):
        response = self.client.get('/schema')

        self.assertEqual({
                             "$schema": "http://json-schema.org/draft-04/hyper-schema#",
                             "definitions": {
                                 "_pagination": {
                                     "properties": {
                                         "per_page": {
                                             "minimum": 1,
                                             "type": "integer",
                                             "default": 20,
                                             "maximum": 100
                                         },
                                         "page": {
                                             "minimum": 1,
                                             "type": "integer",
                                             "default": 1
                                         }
                                     },
                                     "type": "object"
                                 }
                             },
                             "properties": {
                                 "fruit": {
                                     "$ref": "/fruit/schema#"
                                 },
                                 "vegetable": {
                                     "$ref": "/vegetable/schema#"
                                 }
                             }
                         }, response.json)
