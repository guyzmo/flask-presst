from flask_sqlalchemy import SQLAlchemy
import six
from sqlalchemy.orm import backref
from flask_presst import ModelResource, fields, Relationship, SchemaParser
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
            tree = db.relationship(Tree, backref=backref('fruits', lazy='dynamic'))

        db.create_all()

        self.Fruit = Fruit
        self.Tree = Tree

        class TreeResource(ModelResource):
            class Meta:
                model = Tree
                title = 'Tree -- A Tall Plant'

            fruits = Relationship('Fruit')

        class FruitResource(ModelResource):
            class Meta:
                model = Fruit

            tree = fields.ToOne(TreeResource)

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

    def test_create_no_json(self):
        response = self.client.post('/fruit', data='invalid')
        self.assert400(response)

    def test_create_json_string(self):
        response = self.client.post('/fruit', data='invalid', force_json=True)
        self.assert400(response)

    def test_create(self):
        self.request('POST', '/fruit', {'name': 'Apple'},
                     {'sweetness': 5, 'name': 'Apple', '_uri': '/fruit/1', 'tree': None}, 200)

        self.request('POST', '/fruit', {'name': 'Apple', 'sweetness': 9001},
                     {'sweetness': 9001, 'name': 'Apple', '_uri': '/fruit/2', 'tree': None}, 200)

        self.request('POST', '/fruit', {'sweetness': 1}, None, 400)

        self.request('POST', '/tree', {'name': 'Apple'}, {'name': 'Apple', '_uri': '/tree/1'}, 200)

        self.request('POST', '/fruit', {'name': 'Apple', 'tree': '/tree/1'},
                     {'sweetness': 5, 'name': 'Apple', '_uri': '/fruit/3', 'tree': '/tree/1'}, 200)


    def test_get(self):
        apple = lambda id: {'sweetness': 5, 'name': 'Apple', '_uri': '/fruit/{}'.format(id), 'tree': None}

        for i in range(1, 10):
            self.request('POST', '/fruit', {'name': 'Apple'}, apple(i), 200)
            self.request('GET', '/fruit', None, [apple(i) for i in range(1, i + 1)], 200)
            self.request('GET', '/fruit/{}'.format(i), None, apple(i), 200)
            self.request('GET', '/fruit/{}'.format(i + 1), None, None, 404)

    def test_pagination(self):
        apple = lambda id: {'sweetness': 5, 'name': 'Apple', '_uri': '/fruit/{}'.format(id), 'tree': None}

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
                     {'sweetness': 5, 'name': 'Apple', '_uri': '/fruit/1', 'tree': None}, 200)

        # TODO implement support for ColumnDefault
        # FIXME defaults with update
        # self.request('POST', '/fruit/1', {'name': 'Golden Apple'},
        #              {'sweetness': 5, 'name': 'Golden Apple', '_uri': '/fruit/1', 'tree': None}, 200)

        self.request('POST', '/fruit/1', {'name': 'Golden Apple', 'sweetness': 0},
                     {'sweetness': 0, 'name': 'Golden Apple', '_uri': '/fruit/1', 'tree': None}, 200)

        self.request('POST', '/fruit/1', {}, None, 400)

    def test_patch(self):

        self.request('POST', '/tree', {'name': 'Apple tree'}, {'name': 'Apple tree', '_uri': '/tree/1'}, 200)

        expected_apple = {'sweetness': 5, 'name': 'Apple', '_uri': '/fruit/1', 'tree': None}
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
            expected_apple.update(change)
            self.request('PATCH', '/fruit/1', change, expected_apple, 200)

    def test_delete(self):
        self.request('POST', '/tree', {'name': 'Apple tree'}, {'name': 'Apple tree', '_uri': '/tree/1'}, 200)
        self.request('DELETE', '/tree/1', {'name': 'Apple tree'}, None, 204)
        self.request('DELETE', '/tree/1', {'name': 'Apple tree'}, None, 404)
        self.request('DELETE', '/tree/2', {'name': 'Apple tree'}, None, 404)

    def test_no_model(self):
        class OopsResource(ModelResource):
            class Meta:
                pass

        self.api.add_resource(OopsResource)

    def test_relationship_post(self):
        self.request('POST', '/tree', {'name': 'Apple tree'}, {'name': 'Apple tree', '_uri': '/tree/1'}, 200)
        self.request('GET', '/tree/1/fruits', None, [], 200)

        self.request('POST', '/fruit', {'name': 'Apple'},
                     {'name': 'Apple', '_uri': '/fruit/1', 'sweetness': 5, 'tree': None}, 200)

        self.request('POST', '/tree/1/fruits', '/fruit/1',
                     {'name': 'Apple', '_uri': '/fruit/1', 'sweetness': 5, 'tree': '/tree/1'}, 200)

    def test_relationship_get(self):
        self.test_relationship_post()
        self.request('GET', '/tree/1/fruits', None,
                     [{'name': 'Apple', '_uri': '/fruit/1', 'sweetness': 5, 'tree': '/tree/1'}], 200)

    def test_relationship_delete(self):
        self.test_relationship_post()
        self.request('DELETE', '/tree/1/fruits', '/fruit/1', None, 204)
        #self.request('GET', '/apple/seed_count', None, 2, 200)

    maxDiff = None

    def test_get_schema(self):
        self.maxDiff = None

        expected_api_level_schema = {
                             'properties': {
                                 'tree': {
                                     '$ref': '/tree/schema#'
                                 },
                                 'fruit': {
                                     '$ref': '/fruit/schema#'
                                 }
                             },
                             'definitions': {
                                 '_pagination': {
                                     'type': 'object',
                                     'properties': {
                                         'page': {
                                             'type': 'integer',
                                             'default': 1,
                                             'minimum': 1
                                         },
                                         'per_page': {
                                             'type': 'integer',
                                             'default': 100,
                                             'maximum': 100,
                                             'minimum': 1
                                         }
                                     }
                                 }
                             },
                             '$schema': 'http://json-schema.org/draft-04/hyper-schema#'
        }

        expected_fruit_schema = {
            "definitions": {
                "tree": {
                    "oneOf": [
                        {"$ref": "/tree/schema#/definitions/_uri"},
                        {"$ref": "/tree/schema#"},
                        {"type": "null"}
                    ]
                },
                "name": {
                    "type": "string",
                    "maxLength": 60
                },
                "sweetness": {
                    "type": ["integer", "null"],
                    "default": 5,
                },
                "_uri": {
                    "type": "string",
                    "readOnly": True,
                    "format": "uri"
                }
            },
            "properties": {
                "tree": {
                    "$ref": "#/definitions/tree"
                },
                "name": {
                    "$ref": "#/definitions/name"
                },
                "sweetness": {
                    "$ref": "#/definitions/sweetness"
                },
                "_uri": {
                    "$ref": "#/definitions/_uri"
                }
            },
            "required": ["name"],
            'type': 'object',
            "links": [
                {
                    "method": "GET",
                    "href": "/fruit/{id}",
                    "rel": "self"
                },
                {
                    "method": "GET",
                    "href": "/fruit",
                    "rel": "instances",
                    "schema": {
                        "$ref": "/schema#/definitions/_pagination"
                    }
                }
            ]
        }

        expected_tree_schema = {
            'title': 'Tree -- A Tall Plant',
            'definitions': {
                '_uri': {
                    'readOnly': True,
                    'type': 'string',
                    'format': 'uri'
                },
                'name': {
                    'type': 'string',
                    "maxLength": 60
                }
            },
            'properties': {
                '_uri': {
                    '$ref': '#/definitions/_uri'
                },
                'name': {
                    '$ref': '#/definitions/name'
                }
            },
            'required': ['name'],
            'type': 'object',
            'links': [
                {
                    'href': '/tree/{id}',
                    'rel': 'self',
                    'method': 'GET'
                }, {
                    'href': '/tree',
                    'rel': 'instances',
                    'method': 'GET',
                    'schema': {
                        '$ref': '/schema#/definitions/_pagination'
                    }
                },

                {
                    'href': '/tree/{id}/fruits',
                    'method': 'GET',
                    'rel': 'fruits',
                    'schema': {'$ref': '/schema#/definitions/_pagination'},
                    'targetSchema': {
                        'items': {'$ref': '/fruit/schema#'},
                        'type': 'array'
                    }
                },
                {
                    'href': '/tree/{id}/fruits',
                    'method': 'POST',
                    'rel': 'fruits:create',
                    'schema': {
                        'oneOf': [
                            {'$ref': '/fruit/schema#/definitions/_uri'},
                            {'$ref': '/fruit/schema#'},
                            {
                                'items': {
                                    'oneOf': [
                                        {'$ref': '/fruit/schema#/definitions/_uri'},
                                        {'$ref': '/fruit/schema#'}
                                    ]
                                },
                                'type': 'array'
                            }
                        ]
                    }
                },
                {
                    'href': '/tree/{id}/fruits',
                    'method': 'DELETE',
                    'rel': 'fruits:delete',
                    'schema': {
                        'oneOf': [
                            {'$ref': '/fruit/schema#/definitions/_uri'},
                            {
                                'items': {
                                    '$ref': '/fruit/schema#/definitions/_uri'
                                },
                                'type': 'array'
                            }
                        ]
                    }
                },
            ],
        }

        self.assertEqual(expected_fruit_schema, self.client.get('/fruit/schema').json)
        self.assertEqual(expected_tree_schema, self.client.get('/tree/schema').json)


class TestModelResourceFields(PresstTestCase):
    def setUp(self):
        super(TestModelResourceFields, self).setUp()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True

        self.db = db = SQLAlchemy(app)

        class Type(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

        class Machine(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

            type_id = db.Column(db.Integer, db.ForeignKey(Type.id))
            type = db.relationship(Type, backref=backref('machines', lazy='dynamic', uselist=True))

        db.create_all()

        class MachineResource(ModelResource):
            class Meta:
                model = Machine

            type = fields.ToOne('type')

        class TypeResource(ModelResource):
            class Meta:
                model = Type

            machines = fields.ToMany(MachineResource)

        self.api.add_resource(MachineResource)
        self.api.add_resource(TypeResource)

    def test_to_many_kv(self):
        type_kv = fields.ToManyKV('type', embedded=True)

        self.client.post('/type', data=[{'name': 'Foo'}, {'name': 'Bar'}])

        self.assertEqual({
                             'first': {'_uri': '/type/1', 'machines': [], 'name': 'Foo'},
                             'second': {'_uri': '/type/2', 'machines': [], 'name': 'Bar'}
                         }, type_kv.format(type_kv.parse({'first': six.text_type('/type/1'),
                                                          'second': six.text_type('/type/2')})))

        self.assertEqual({}, type_kv.convert({}))

        parser = SchemaParser({'types': fields.ToManyKV('type', default={})})
        self.assertEqual({'types': {}}, parser.parse({}))

    def test_nested(self):
        type_nested = fields.Nested({'type': fields.ToOne('type'), 'int': fields.Integer()})

        self.client.post('/type', data={'name': 'Foo'})

        self.assertEqual({'int': 123, 'type': '/type/1'}, type_nested.format(
            type_nested.parse({'type': six.text_type('/type/1'), 'int': 123})))

        self.assertEqual(None, type_nested.convert(None))

    def test_nested_read_only(self):
        type_nested = fields.Nested({'type': fields.ToOne('type'), 'int': fields.Integer()}, read_only=['type'])

        self.assertEqual({
                             'type': ['object', 'null'],
                             'properties': {
                                 'type': {
                                     'oneOf': [
                                         {'$ref': '/type/schema#/definitions/_uri'},
                                         {'$ref': '/type/schema#'},
                                         {'type': 'null'},
                                     ],
                                     'readOnly': True
                                 },
                                 'int': {'type': ['integer', 'null']
                                 }
                             }
                         }, type_nested.schema)

        self.client.post('/type', data={'name': 'Foo'})

        self.assertEqual({'int': 123, 'type': None}, type_nested.format(
            type_nested.parse({'type': six.text_type('/type/1'), 'int': 123})))

        self.assertEqual({'int': 123, 'type': '/type/1'},
                         type_nested.format({'type': fields.ToOne('type').parse(six.text_type('/type/1')), 'int': 123}))

        self.assertEqual(None, type_nested.convert(None))


    def test_post_to_many(self):
        self.request('POST', '/machine', {'name': 'Press I'},
                     {'name': 'Press I', '_uri': '/machine/1', 'type': None}, 200)

        self.request('POST', '/type', {'name': 'Press', 'machines': ['/machine/1']},
                     {'name': 'Press', '_uri': '/type/1', 'machines': ['/machine/1']}, 200)