from functools import wraps
import unittest
from flask import current_app, request
from flask.ext.principal import Identity, identity_changed, identity_loaded, RoleNeed, UserNeed, Principal, ItemNeed
from flask.ext.restful import abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.testing.pickleable import User
from flask.ext.presst import Relationship, fields
from flask.ext.presst.principal.resource import PrincipalResource
from sqlalchemy.orm import backref
from tests import PresstTestCase, ApiClient


class AuthorizedApiClient(ApiClient):
    def open(self, *args, **kw):
        """
        Sends HTTP Authorization header with  the ``HTTP_AUTHORIZATION`` config value
        unless :param:`authorize` is ``False``.
        """
        auth = kw.pop('auth', True)
        headers = kw.pop('headers', [])

        if auth:
            headers.append(('Authorization', 'Basic OnBhc3N3b3Jk'))
        return super(AuthorizedApiClient, self).open(*args, headers=headers, **kw)

class PrincipalResourceTestCase(PresstTestCase):

    def create_app(self):
        app = super(PrincipalResourceTestCase, self).create_app()
        app.test_client_class = AuthorizedApiClient

        self.principal = Principal(app)
        self.db = db = SQLAlchemy(app)

        class User(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String())

        class BookStore(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String())

            owner_id = db.Column(db.Integer, db.ForeignKey(User.id))
            owner = db.relationship(User, backref=backref('stores', lazy='dynamic'))

        class Book(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            title = db.Column(db.String(), nullable=False)

            author_id = db.Column(db.Integer, db.ForeignKey(User.id))
            author = db.relationship(User, backref=backref('books', lazy='dynamic'))

        class BookSigning(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            book_id = db.Column(db.Integer, db.ForeignKey(Book.id), nullable=False)
            store_id = db.Column(db.Integer, db.ForeignKey(BookStore.id), nullable=False)

            book = db.relationship(Book)
            store = db.relationship(BookStore)

        db.create_all()

        for model in (BookStore, User, Book, BookSigning):
            setattr(self, model.__tablename__.upper(), model)

        return app

    def setUp(self):
        super(PrincipalResourceTestCase, self).setUp()
        self.mock_user = None

        @identity_loaded.connect_via(self.app)
        def on_identity_loaded(sender, identity):
            identity.provides.add(UserNeed(identity.id))

            for role in self.mock_user.get('roles', []):
                identity.provides.add(RoleNeed(role))

            for need in self.mock_user.get('needs', []):
                identity.provides.add(need)

        def authenticate(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                auth = request.authorization

                if not auth:
                    abort(401, message='Authorization required')

                if auth.password == 'password':
                    identity_changed.send(current_app._get_current_object(), identity=Identity(self.mock_user['id']))
                else:
                    abort(401, message="Unauthorized")
                return fn(*args, **kwargs)
            return wrapper

        self.authenticate = authenticate

        class AuthResource(PrincipalResource):
            method_decorators = [self.authenticate]

        self.AuthResource = AuthResource


    def test_role(self):

        class BookResource(self.AuthResource):

            class Meta:
                model = self.BOOK
                permissions = {
                    'create': 'author'
                }

        self.api.add_resource(BookResource)

        response = self.client.post('/book', data={'title': 'Foo'}, auth=False)
        self.assert401(response)

        self.mock_user = {'id': 1}
        response = self.client.post('/book', data={'title': 'Foo'})
        self.assert403(response)

        self.mock_user = {'id': 1, 'roles': ['author']}
        response = self.client.post('/book', data={'title': 'Foo'})
        self.assert200(response)
        self.assertEqual({'title': 'Foo', '_uri': '/book/1'}, response.json)

        self.assert200(self.client.post('/book/1', data={'title': 'Foo I'}))

        self.mock_user = {'id': 1}
        self.assert403(self.client.post('/book/1', data={'title': 'Bar'}))

        self.assert403(self.client.delete('/book/1'))

        # self.user = {'id': 1, 'roles': ['author']}
        # self.assert200(self.client.delete('/book/1'))

        # response = self.client.post('/book', data={'title': 'Foo'})
        #
        # self.assert200(response)


    def test_inherit_role_to_one_field(self):

        class BookStoreResource(self.AuthResource):
            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': ['admin']
                }

        class BookSigningResource(self.AuthResource):
            book = fields.ToOne('book')
            store = fields.ToOne('book_store')

            class Meta:
                model = self.BOOK_SIGNING
                permissions = {
                    'create': 'update:store'
                }

        class BookResource(self.AuthResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'create': 'yes'
                }

        self.api.add_resource(BookStoreResource)
        self.api.add_resource(BookSigningResource)
        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.assert200(self.client.post('/book_store', data={
            'name': 'Foo Books'
        }))

        self.assert200(self.client.post('/book', data={
            'title': 'Bar'
        }))

        self.mock_user = {'id': 2}
        self.assert403(self.client.post('/book_signing', data={'book': '/book/1', 'store': '/book_store/1'}))

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.assert200(self.client.post('/book_signing', data={'book': '/book/1', 'store': '/book_store/1'}))

    def test_user_need(self):

        class BookStoreResource(self.AuthResource):
            books = Relationship('book')
            owner = fields.ToOne('user')

            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': ['admin', 'user:owner']
                }

        class UserResource(self.AuthResource):
            class Meta:
                model = self.USER
                permissions = {
                    'create': 'admin'
                }

        self.api.add_resource(BookStoreResource)
        self.api.add_resource(UserResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}

        self.assert200(self.client.post('/user', data={'name': 'Admin'}))

        response = self.client.post('/book_store', data=[
            {
                'name': 'Books & More',
                'owner': {
                    'name': 'Mr. Moore'
                }
            },
            {
                'name': 'Foo Books',
                'owner': {
                    'name': 'Foo'
                }
            }
        ])

        self.assertEqual([
            {'_uri': '/book_store/1', 'name': 'Books & More', 'owner': '/user/2'},
            {'_uri': '/book_store/2', 'name': 'Foo Books', 'owner': '/user/3'}
        ], response.json)

        response = self.client.patch('/book_store/1', data={'name': 'books & moore'})
        self.assert200(response)

        self.mock_user = {'id': 3}
        response = self.client.patch('/book_store/1', data={'name': 'Books & Foore'})
        self.assert403(response)

        self.mock_user = {'id': 2}
        response = self.client.patch('/book_store/1', data={'name': 'Books & Moore'})

        self.assert200(response)

        self.assertEqual({
                             '_uri': '/book_store/1',
                             'name': 'Books & Moore',
                             'owner': '/user/2'
                         }, response.json)

        response = self.client.patch('/book_store/2', data={'name': 'Moore Books'})
        self.assert403(response)

    def test_item_need_update(self):

        class BookStoreResource(self.AuthResource):
            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': 'update'
                }

        self.api.add_resource(BookStoreResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}

        response = self.client.post('/book_store', data=[
            {'name': 'Bar Books'},
            {'name': 'Foomazon'}
        ])

        self.assert200(response)

        self.mock_user = {'id': 1, 'needs': [ItemNeed('update', 2, 'book_store')]}

        self.assert403(self.client.post('/book_store/1', data={'name': 'Foo'}))

        response = self.client.post('/book_store/2', data={'name': 'Foo'})
        self.assert200(response)
        self.assertEqual({'_uri': '/book_store/2', 'name': 'Foo'}, response.json)

        # TODO DELETE

    def test_yes_no(self):
        class BookResource(self.AuthResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': 'yes',
                    'create': 'admin',
                    'update': 'no'
                }

        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.assert200(self.client.post('/book', data={'title': 'Foo'}))
        self.assert403(self.client.post('/book/1', data={'title': 'Bar'}))
        self.assert200(self.client.get('/book/1'))
        self.assert200(self.client.get('/book'))

    def test_item_need_read(self):

        class BookResource(self.AuthResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': ['owns-copy', 'admin'],
                    'create': 'admin',
                    'owns-copy': 'owns-copy'
                }

        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}

        response = self.client.post('/book', data=[
            {'title': 'GoT Vol. {}'.format(i + 1)} for i in range(20)
        ])

        self.assertEqual(20, len(response.json))
        self.assertEqual(20, len(self.client.get('/book').json))

        self.mock_user = {'id': 2, 'needs': [ItemNeed('owns-copy', i, 'book') for i in (1,4,6,8,11,15,19)]}
        self.assertEqual(7, len(self.client.get('/book').json))

        self.mock_user = {'id': 3, 'needs': [ItemNeed('owns-copy', i, 'book') for i in (2,7,19)]}
        self.assertEqual([
                             {'_uri': '/book/2', 'title': 'GoT Vol. 2'},
                             {'_uri': '/book/7', 'title': 'GoT Vol. 7'},
                             {'_uri': '/book/19', 'title': 'GoT Vol. 19'}
                         ], self.client.get('/book').json)

        self.assert404(self.client.get('/book/15'))
        self.assert200(self.client.get('/book/2'))
        self.assert200(self.client.get('/book/7'))
        self.assert404(self.client.get('/book/1'))
        self.assert404(self.client.get('/book/99'))

        self.mock_user = {'id': 4}
        self.assertEqual([], self.client.get('/book').json)


    @unittest.SkipTest
    def test_relationship(self):
        "should require update permission on parent resource for updating, read permissions on both"
        pass

    @unittest.SkipTest
    def test_item_action(self):
        "should require read permission on parent resource plus any additional permissions"
        pass

    def test_permission_circular(self):
        class BookResource(self.AuthResource):
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': 'create',
                    'create': 'read',
                    'update': 'create',
                    'delete': 'update'
                }

        self.api.add_resource(BookResource)

        with self.assertRaises(RuntimeError):
            BookResource._needs
