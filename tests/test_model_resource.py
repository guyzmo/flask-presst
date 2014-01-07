from flask.ext.sqlalchemy import SQLAlchemy
from flask_presst import ModelResource, fields, PolymorphicModelResource
from tests import PresstTestCase


class TestModelResource(PresstTestCase):
    def setUp(self):
        super(TestModelResource, self).setUp()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True

        self.db = db = SQLAlchemy(app)

        class Tree(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

        class Fruit(db.Model):
            fruit_id = db.Column(db.Integer, primary_key=True)

            name = db.Column(db.String(60), nullable=False)
            sweetness = db.Column(db.Integer, default=5)

            tree_id = db.Column(db.Integer, db.ForeignKey(Tree.id))
            tree = db.relationship(Tree)

        db.create_all()

        self.Fruit = Fruit
        self.Tree = Tree

        class TreeResource(ModelResource):
            class Meta:
                model = Tree

        class FruitResource(ModelResource):
            class Meta:
                model = Fruit

            tree = fields.ToOneField(TreeResource)

        self.api.add_resource(FruitResource)
        self.api.add_resource(TreeResource)

        self.FruitResource = FruitResource
        self.TreeResource = TreeResource

    def tearDown(self):
        self.db.drop_all()

    def test_field_discovery(self):
        self.assertEqual(set(self.TreeResource._fields.keys()), {'name'})
        self.assertEqual(set(self.FruitResource._fields.keys()), {'name', 'sweetness', 'tree'})
        self.assertEqual(self.FruitResource.resource_name, 'fruit')
        self.assertEqual(self.TreeResource.resource_name, 'tree')

    def test_create(self):
        self.request('POST', '/fruit', {'name': 'Apple'},
                     {'sweetness': 5, 'name': u'Apple', 'resource_uri': u'/fruit/1', u'tree': None}, 200)

        self.request('POST', '/fruit', {'name': 'Apple', 'sweetness': 9001},
                     {'sweetness': 9001, 'name': u'Apple', 'resource_uri': u'/fruit/2', 'tree': None}, 200)

        self.request('POST', '/fruit', {'sweetness': 1}, None, 400)

        self.request('POST', '/tree', {'name': 'Apple'},{'name': u'Apple', 'resource_uri': u'/tree/1'}, 200)

        self.request('POST', '/fruit', {'name': 'Apple', 'tree': '/tree/1'},
                     {'sweetness': 5, 'name': u'Apple', 'resource_uri': u'/fruit/3', 'tree': '/tree/1'}, 200)


    def test_get(self):
        apple = lambda id: {u'sweetness': 5, u'name': u'Apple', u'resource_uri': u'/fruit/{}'.format(id), u'tree': None}

        for i in range(1, 10):
            print i
            self.request('POST', '/fruit', {'name': 'Apple'}, apple(i), 200)
            self.request('GET', '/fruit', None, [apple(i) for i in range(1, i + 1)], 200)

    def test_pagination(self):
        apple = lambda id: {u'sweetness': 5, u'name': u'Apple', u'resource_uri': u'/fruit/{}'.format(id), u'tree': None}

        for i in range(1, 10):
            self.request('POST', '/fruit', {'name': 'Apple'}, apple(i), 200)

        with self.app.test_client() as client:

            response = client.get('/fruit')
            self.assertEqual(response.headers['Link'],
                             '</fruit?page=1&per_page=20>; rel="self"')

            response = client.get('/fruit?per_page=5')
            self.assertEqual(set(response.headers['Link'].split(',')),
                             {'</fruit?page=1&per_page=5>; rel="self"',
                              '</fruit?page=2&per_page=5>; rel="last"',
                              '</fruit?page=2&per_page=5>; rel="next"'})

            response = client.get('/fruit?page=1&per_page=5')
            self.assertEqual(set(response.headers['Link'].split(',')),
                             {'</fruit?page=1&per_page=5>; rel="self"',
                              '</fruit?page=2&per_page=5>; rel="last"',
                              '</fruit?page=2&per_page=5>; rel="next"'})

            response = client.get('/fruit?page=2&per_page=5')
            self.assertEqual(set(response.headers['Link'].split(',')),
                             {'</fruit?page=2&per_page=5>; rel="self"',
                              '</fruit?page=1&per_page=5>; rel="first"',
                              '</fruit?page=1&per_page=5>; rel="prev"'})

            response = client.get('/fruit?page=2&per_page=2')
            self.assertEqual(set(response.headers['Link'].split(',')),
                             {'</fruit?page=3&per_page=2>; rel="next"',
                              '</fruit?page=5&per_page=2>; rel="last"',
                              '</fruit?page=1&per_page=2>; rel="prev"',
                              '</fruit?page=1&per_page=2>; rel="first"',
                              '</fruit?page=2&per_page=2>; rel="self"'})


    def test_update(self):
            self.request('POST', '/fruit', {'name': 'Apple'},
                         {'sweetness': 5, 'name': u'Apple', 'resource_uri': u'/fruit/1', u'tree': None}, 200)

            # TODO implement support for ColumnDefault
            # FIXME defaults with update
            # self.request('POST', '/fruit/1', {'name': 'Golden Apple'},
            #              {'sweetness': 5, 'name': u'Golden Apple', 'resource_uri': u'/fruit/1', u'tree': None}, 200)

            self.request('POST', '/fruit/1', {'name': 'Golden Apple', 'sweetness': 0},
                         {'sweetness': 0, 'name': u'Golden Apple', 'resource_uri': u'/fruit/1', u'tree': None}, 200)

            self.request('POST', '/fruit/1', {}, None, 400)

    def test_patch(self):

        self.request('POST', '/tree', {'name': 'Apple tree'}, {'name': u'Apple tree', 'resource_uri': u'/tree/1'}, 200)

        expected_apple = {'sweetness': 5, 'name': u'Apple', 'resource_uri': u'/fruit/1', u'tree': None}
        self.request('POST', '/fruit', {'name': 'Apple'}, expected_apple, 200)

        changes = [
            {'name': 'Golden Apple'},
            {'name': 'Golden Apple'},
            {'tree': '/tree/1'},
            {'sweetness': 3},
            {},
            {'name': 'Golden Apple', 'tree': None},
        ]

        for change in changes:
            print 'expected_apple, change:',expected_apple, change
            expected_apple.update(change)
            self.request('PATCH', '/fruit/1', change, expected_apple, 200)

    def test_delete(self):
        self.request('POST', '/tree', {'name': 'Apple tree'}, {'name': u'Apple tree', 'resource_uri': u'/tree/1'}, 200)
        self.request('DELETE', '/tree/1', {'name': 'Apple tree'}, None, 204)
        self.request('DELETE', '/tree/1', {'name': 'Apple tree'}, None, 404)
        self.request('DELETE', '/tree/2', {'name': 'Apple tree'}, None, 404)


class TestPolymorphicModelResource(PresstTestCase):
    def setUp(self):
        super(TestPolymorphicModelResource, self).setUp()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True
        self.db = db = SQLAlchemy(app)

        class Fruit(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)
            table = db.Column(db.String(60))
            color = db.Column(db.String)

            __mapper_args__ = {
                'polymorphic_identity': 'fruit',
                'polymorphic_on': table
            }

        class CitrusFruit(Fruit):
            id = db.Column(db.Integer, db.ForeignKey(Fruit.id), primary_key=True)
            sweetness = db.Column(db.Integer)

            __mapper_args__ = {
                'polymorphic_identity': 'citrus',
            }

        class FruitResource(PolymorphicModelResource):
            class Meta:
                model = Fruit
                exclude_fields = ['table']

        class CitrusFruitResource(ModelResource):
            class Meta:
                model = CitrusFruit
                resource_name = 'citrus'
                exclude_fields = ['table']

        db.create_all()

        self.api.add_resource(FruitResource)
        self.api.add_resource(CitrusFruitResource)

    def test_polymorphic(self):
        self.request('POST', '/fruit', {'name': 'Banana', 'color': 'yellow'},
                     {'name': 'Banana', 'color': 'yellow', 'resource_uri': u'/fruit/1'}, 200)

        self.request('POST', '/citrus', {'name': 'Lemon', 'color': 'yellow'},
                     {'name': 'Lemon', 'sweetness': 0, 'color': 'yellow', 'resource_uri': u'/citrus/2'}, 200)

        self.request('GET', '/fruit', None, [
            {u'color': u'yellow', u'name': u'Banana', u'resource_uri': u'/fruit/1'},
            {u'citrus': {u'color': u'yellow',
                         u'name': u'Lemon',
                         u'resource_uri': u'/citrus/2',
                         u'sweetness': 0},
             u'color': u'yellow',
             u'name': u'Lemon',
             u'resource_uri': u'/fruit/2'}
        ], 200)
