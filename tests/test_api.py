from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.presst import fields, ModelResource
from tests import PresstTestCase, TestPresstResource

class VegetableResource(TestPresstResource):
    name = fields.String()
    class Meta:
        resource_name = 'vegetable'

class TestReference(PresstTestCase):
    def setUp(self):
        super(TestReference, self).setUp()

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
        self.assertEqual(self.api.get_resource_class('{}.VegetableResource'.format(self.__module__)), self.VegetableResource)
        self.assertEqual(self.api.get_resource_class('VegetableResource', module_name=self.__module__), self.VegetableResource)

    def test_get_resource_for_model(self):
        self.assertEqual(self.api.get_resource_for_model(self.Fruit), self.FruitResource)
        self.assertEqual(self.api.get_resource_for_model(self.Pet), None)
