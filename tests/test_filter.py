import unittest

from flask_sqlalchemy import SQLAlchemy

from flask_presst import ModelResource, fields
from tests import PresstTestCase


__author__ = 'lyschoening'


class FilterTestCase(PresstTestCase):
    def setUp(self):
        super(FilterTestCase, self).setUp()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True

        self.db = db = SQLAlchemy(app)

        class User(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            first_name = db.Column(db.String(60), nullable=False)
            last_name = db.Column(db.String(60), nullable=False)

            gender = db.Column(db.String(1))

            age = db.Column(db.Integer)

            is_staff = db.Column(db.Boolean, default=None)

        db.create_all()

        class UserResource(ModelResource):
            gender = fields.String(enum=['f', 'm'])

            class Meta:
                model = User

        class AllowUserResource(ModelResource):
            class Meta:
                model = User
                resource_name = 'allow-user'
                allowed_filters = {
                    'first_name': ['$eq'],
                    'is_staff': '*'
                }

        self.api.add_resource(UserResource)
        self.api.add_resource(AllowUserResource)

    def post_sample_set_a(self):
        response = self.client.post('/user', data=[
            {'first_name': 'John', 'last_name': 'Doe', 'age': 32, 'is_staff': True, 'gender': 'm'},
            {'first_name': 'Jonnie', 'last_name': 'Doe', 'age': 25, 'is_staff': False, 'gender': 'm'},
            {'first_name': 'Jane', 'last_name': 'Roe', 'age': 18, 'is_staff': False, 'gender': 'f'},
            {'first_name': 'Joe', 'last_name': 'Bloggs', 'age': 21, 'is_staff': True, 'gender': 'm'},
            {'first_name': 'Sue', 'last_name': 'Watts', 'age': 25, 'is_staff': True}
        ])

        self.assert200(response)

    def test_equality(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"last_name": "Doe"}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": 25}')

        self.assertEqualWithout([
                                    {'first_name': 'Jonnie', 'last_name': 'Doe', 'age': 25},
                                    {'first_name': 'Sue', 'last_name': 'Watts', 'age': 25},
                                ], response.json, without=['_uri', 'gender', 'is_staff'])

        response = self.client.get('/user?where={"last_name": "Doe", "age": 25}')

        self.assertEqualWithout([
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

    def test_inequality(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"last_name": {"$ne": "Watts"}, "age": {"$ne": 32}}')

        self.assertEqualWithout([
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$gt": 25}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'}
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$gte": 25}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Sue', 'last_name': 'Watts'},
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$lte": 21}}')

        self.assertEqualWithout([
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'}
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$lt": 21.0}}')

        self.assertEqualWithout([
                                    {'first_name': 'Jane', 'last_name': 'Roe'}
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"age": {"$lt": null}}')
        self.assert400(response)

        response = self.client.get('/user?where={"first_name": {"$gt": "Jo"}}')
        self.assert400(response)

    def test_in(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"last_name": {"$in": ["Bloggs", "Watts"]}}')

        self.assertEqualWithout([
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                    {'first_name': 'Sue', 'last_name': 'Watts'}
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"last_name": {"$in": []}}')

        self.assertEqualWithout([], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

    def test_startswith(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"first_name": {"$startswith": "Jo"}}')

        self.assertEqualWithout([
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'}
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?where={"first_name": {"$startswith": "J%e"}}')

        self.assertEqualWithout([], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

    @unittest.SkipTest
    def test_text_search(self):
        self.post_sample_set_a()

        response = self.client.get('/user?search=sbc+dedf&rank=1')

    def test_sort(self):
        self.post_sample_set_a()

        response = self.client.get('/user?sort={"last_name": -1, "first_name": 1}')

        self.assert200(response)
        self.assertEqualWithout([
                                    {'first_name': 'Sue', 'last_name': 'Watts'},
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'}
                                ], response.json,
                                without=['_uri', 'gender', 'age', 'is_staff'])

        response = self.client.get('/user?sort={"age": 1, "first_name": 1}')

        self.assertEqualWithout([
                                    {'first_name': 'Jane', 'last_name': 'Roe'},
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'},
                                    {'first_name': 'Sue', 'last_name': 'Watts'},
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                ], response.json,
                                without=['_uri', 'gender', 'age', 'is_staff'])


    def test_sort_and_where(self):
        self.post_sample_set_a()

        response = self.client.get('/user?where={"first_name": {"$startswith": "Jo"}}&sort={"first_name": 1}')

        self.assertEqualWithout([
                                    {'first_name': 'Joe', 'last_name': 'Bloggs'},
                                    {'first_name': 'John', 'last_name': 'Doe'},
                                    {'first_name': 'Jonnie', 'last_name': 'Doe'}
                                ], response.json, without=['_uri', 'gender', 'age', 'is_staff'])

    def test_sort_pages(self):
        pass

    def test_disallowed_where_filters(self):
        pass

    def test_schema(self):
        pass


if __name__ == '__main__':
    unittest.main()