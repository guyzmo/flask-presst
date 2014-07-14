from collections import defaultdict
from unittest import SkipTest
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask.ext.presst import ModelResource, Relationship, fields
from tests import PresstTestCase, SimpleResource


class TestResourceBulkEmbedded(PresstTestCase):
    def setUp(self):
        super(TestResourceBulkEmbedded, self).setUp()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'

        self.db = db = SQLAlchemy(app)

        class City(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

        class Street(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            city_id = db.Column(db.Integer, db.ForeignKey(City.id), nullable=False)

            name = db.Column(db.String(60), nullable=False)

            city = db.relationship(City, backref=backref('streets', lazy='dynamic'))

        class StreetAddress(db.Model):
            # TODO support multiple primary keys (must self-define).
            id = db.Column(db.Integer, primary_key=True)
            street_id = db.Column(db.Integer, db.ForeignKey(Street.id), nullable=False)
            number = db.Column(db.Integer, nullable=False)

            street = db.relationship(Street, backref=backref('addresses', lazy='dynamic'))

        # TODO flats or something else with KV store
        #
        # class Flat(db.Model):
        #     id = db.Column(db.Integer, primary_key=True)
        #     address_id = db.Column(db.Integer, db.ForeignKey(StreetAddress.id))
        #
        #     number = db.Column(db.Integer)
        #     floor = db.Column(db.Integer)
        #     side = db.Column(db.String)
        #

        db.create_all()

        class CityResource(ModelResource):
            streets = Relationship('street')

            class Meta:
                model = City

        class StreetResource(ModelResource):
            city = fields.ToOne('city')
            addresses = fields.ToMany('address', embedded=True)

            class Meta:
                model = Street

        class StreetAddressResource(ModelResource):
            street = fields.ToOne('street')

            class Meta:
                resource_name = 'address'
                model = StreetAddress

        self.api.add_resource(CityResource)
        self.api.add_resource(StreetResource)
        self.api.add_resource(StreetAddressResource)

    def test_create_embedded_one(self):
        response = self.client.post('/street', data={
            'city': {'name': 'Berlin'},
            'name': 'Unter den Linden'
        })

        self.assert200(response)
        self.assertEqual(response.json, {
            'resource_uri': '/street/1',
            'name': 'Unter den Linden',
            'city': '/city/1',
            'addresses': []
        })

    def test_create_embedded_many(self):
        self.assert200(self.client.post('/city', data={'name': 'Copenhagen'}))

        # TODO repeat with /city/1/streets
        response = self.client.post('/street', data={
            'city': '/city/1',
            'name': 'Noerrebrogade',
            'addresses': [
                {'number': 1},
                {'number': 2},
                {'number': 3}
            ]
        })

        self.assert200(response)
        self.assertEqual(response.json,
                         {'addresses': [{'number': 1,
                                         'resource_uri': '/address/1',
                                         'street': '/street/1'},
                                        {'number': 2,
                                         'resource_uri': '/address/2',
                                         'street': '/street/1'},
                                        {'number': 3,
                                         'resource_uri': '/address/3',
                                         'street': '/street/1'}],
                          'city': '/city/1',
                          'name': 'Noerrebrogade',
                          'resource_uri': '/street/1'})

    def test_create_bulk(self):
        response = self.client.post('/city', data=[
            {'name': 'Aarhus'},
            {'name': 'Copenhagen'},
            {'name': 'Roskilde'}
        ])

        self.assert200(response)
        self.assertEqual(response.json, [
            {'name': 'Aarhus', 'resource_uri': '/city/1'},
            {'name': 'Copenhagen', 'resource_uri': '/city/2'},
            {'name': 'Roskilde', 'resource_uri': '/city/3'}
        ])

    def test_create_bulk_invalid(self):
        response = self.client.post('/city', data=[
            {'name': 'Aarhus'},
            {'foo': 'bar'},
            {'name': 'Roskilde'}
        ])

        self.assert400(response)
        self.assertEqual(response.json, {'message': 'Unknown field: foo'})

        self.assert404(self.client.get('/city/1'))

    def test_create_bulk_relationship(self):
        self.client.post('/city', data={
            'name': 'New Foo'
        })

        response = self.client.post('/city/1/streets', data=[
            {'name': 'Foo Rd.'},
            {'name': 'Bar St.', 'addresses': [{'number': 123}]}
        ])

        expected = [
            {
                'name': 'Foo Rd.',
                'city': '/city/1',
                'resource_uri': '/street/1',
                'addresses': []
            },
            {
                'name': 'Bar St.',
                'city': '/city/1',
                'resource_uri': '/street/2',
                'addresses': [
                    {
                        'street': '/street/2',
                        'resource_uri': '/address/1',
                        'number': 123
                    }
                ]
            },
        ]

        self.assert200(response)
        self.assertEqual(response.json, expected)
        self.assertEqual(self.client.get('/city/1/streets').json, expected)

    def test_create_embedded_recursive(self):
        # NOTE recursion is somewhat difficult to prevent but not currently considered harmful.
        # Where a conflict arises, the solution found by SQLAlchemy
        # (overwriting from child to parent) is typically acceptable.

        # TODO add a new 'allow_update_embedding' attribute to ToOne/Many fields

        self.assert200(self.client.post('/city', data={'name': 'Foo'}))

        response = self.client.post('/street', data={
            'name': 'Foo',
            'city': '/city/1',
            'addresses': [
                {
                    'number': 1,
                    'street': {
                        'name': 'Foo Foo',
                        'city': '/city/1',
                        'addresses': []
                    }
                }
            ]
        })

        self.assert200(response)
        self.assertEqual(response.json, {
            'addresses': [
                {
                    'resource_uri': '/address/1',
                    'street': '/street/2',
                    'number': 1
                }
            ],
            'resource_uri': '/street/2',
            'city': '/city/1',
            'name': 'Foo'
        })

        self.assertEqual(self.client.get('/street').json, [
            {
                'city': '/city/1',
                'resource_uri': '/street/1',
                'addresses': [],
                'name': 'Foo Foo'
            },
            {
                'addresses': [
                    {
                        'street': '/street/2',
                        'number': 1,
                        'resource_uri': '/address/1'
                    }],
                'resource_uri': '/street/2',
                'city': '/city/1',
                'name': 'Foo'
            }

        ])

    def test_create_bulk_embedded(self):
        self.assert200(self.client.post('/city', data={'name': 'Foo'}))

        response = self.client.post('/street', data=[
            {
                'city': '/city/1',
                'name': 'Foo St.',
                'addresses': [
                    {'number': 1},
                ]
            },
            {
                'city': '/city/1',
                'name': 'Bar St.',
                'addresses': [
                    {'number': 1},
                ]
            }
        ])

        self.assertEqual(response.json, [
            {
                'city': '/city/1',
                'addresses': [
                    {
                        'resource_uri': '/address/1',
                        'number': 1,
                        'street': '/street/1'
                    }
                ],
                'resource_uri': '/street/1',
                'name': 'Foo St.'
            },
            {
                'city': '/city/1',
                'addresses': [
                    {
                        'resource_uri': '/address/2',
                        'number': 1,
                        'street': '/street/2'
                    }
                ],
                'resource_uri': '/street/2',
                'name': 'Bar St.'
            }
        ])

    # TODO implement bulk updates (low priority)
    @SkipTest
    def test_update_bulk(self):
        self.client.post('/city', data=[
            {'name': 'BER'},
            {'name': 'CPH'}
        ])

        response = self.client.post('/city/1;2', data=[
            {'name': 'Berlin'},
            {'name': 'Copenhagen'}
        ])

class TestResourceModelMix(PresstTestCase):
    """
    Mixing ModelResource and other Resource types can require a fair amount of hacking. This TestCase only shows
    that doing so is possible in principle.
    """

    def setUp(self):
        super(TestResourceModelMix, self).setUp()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'

        self.db = db = SQLAlchemy(app)

        class City(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

        db.create_all()

        class CityResource(ModelResource):
            tags = Relationship('tag', backref='city')

            class Meta:
                model = City

            @classmethod
            def add_to_relationship(cls, item, relationship, child):
                child['city'] = item
                return child

            @classmethod
            def remove_from_relationship(cls, item, relationship, child):
                TagResource.items.remove(child)
                return child

            @classmethod
            def get_relationship(cls, item, relationship):
                return [tag for tag in TagResource.items if tag['city'].id == item.id]

        class TagResource(SimpleResource):  # TODO change name to simple resource
            items = []

            city = fields.ToOne('city')
            name = fields.String()

            class Meta:
                required_fields = ['city', 'name']
                resource_name = 'tag'  # TODO change to 'endpoint' or 'name'

        self.api.add_resource(CityResource)
        self.api.add_resource(TagResource)

    def test_create_simple(self):

        self.assert200(self.client.post('/city', data={'name': 'Foo'}))

        response = self.client.post('/city/1/tags', data={'name': 'foo'})

        self.assert200(response)
        self.assertEqual(response.json, {
            'city': '/city/1',
            'name': 'foo',
            'resource_uri': '/tag/1'
        })

        self.assert200(self.client.post('/tag', data={'city': '/city/1', 'name': 'bar'}))

        response = self.client.post('/city/1/tags', data={'resource_uri': '/tag/2'})
        self.assert200(response)

        self.assertEqual(self.client.get('/city/1/tags').json, [
            {'city': '/city/1', 'name': 'foo', 'resource_uri': '/tag/1'},
            {'city': '/city/1', 'name': 'bar', 'resource_uri': '/tag/2'}
        ])

    def test_delete_simple(self):
        self.assert200(self.client.post('/city', data={'name': 'Foo'}))

        self.client.post('/city/1/tags', data=[
            {'name': 'foo'},
            {'name': 'bar'},
            {'name': 'bat'}
        ])

        self.assertEqual(len(self.client.get('/city/1/tags').json), 3)

        self.client.delete('/city/1/tags', data=['/tag/1', '/tag/3'], force_json=True)
        self.client.delete('/city/1/tags', data={'resource_uri': '/tag/2'})

        self.assertEqual(self.client.get('/city/1/tags').json, [])