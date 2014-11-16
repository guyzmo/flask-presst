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

        class Group(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String())

        class User(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String())

            group_id = db.Column(db.Integer, db.ForeignKey(Group.id))
            group = db.relationship(Group)

        class BookStore(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String())

            owner_id = db.Column(db.Integer, db.ForeignKey(User.id))
            owner = db.relationship(User, backref=backref('stores', lazy='dynamic'))

            group_id = db.Column(db.Integer, db.ForeignKey(Group.id))
            group = db.relationship(Group)

        class Book(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            title = db.Column(db.String(), nullable=False)

            author_id = db.Column(db.Integer, db.ForeignKey(User.id))
            author = db.relationship(User, backref=backref('books', lazy='dynamic'))

            store_id = db.Column(db.Integer, db.ForeignKey(BookStore.id))
            store = db.relationship(BookStore)

        class BookSigning(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            book_id = db.Column(db.Integer, db.ForeignKey(Book.id), nullable=False)
            store_id = db.Column(db.Integer, db.ForeignKey(BookStore.id), nullable=False)

            book = db.relationship(Book)
            store = db.relationship(BookStore)

        db.create_all()

        for model in (Group, BookStore, User, Book, BookSigning):
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

        self.api.decorators = [authenticate]

    def test_role(self):
        class BookResource(PrincipalResource):

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

        class BookStoreResource(PrincipalResource):
            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': ['admin']
                }

        class BookSigningResource(PrincipalResource):
            book = fields.ToOne('book')
            store = fields.ToOne('book_store')

            class Meta:
                model = self.BOOK_SIGNING
                permissions = {
                    'create': 'update:store'
                }

        class BookResource(PrincipalResource):
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

        class BookStoreResource(PrincipalResource):
            books = Relationship('book')
            owner = fields.ToOne('user')

            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'create': 'admin',
                    'update': ['admin', 'user:owner']
                }

        class UserResource(PrincipalResource):
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

        class BookStoreResource(PrincipalResource):
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
        class BookResource(PrincipalResource):
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

        class BookResource(PrincipalResource):
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

    def test_relationship_group(self):
        "require read permission on a third part resource to access the list of book"

        class GroupResource(PrincipalResource):
            class Meta:
                model = self.GROUP
                permissions = {
                    'read': 'admin',
                    'create': 'admin',
                    'group':'group'
                }

        class BookStoreResource(PrincipalResource):
            group = fields.ToOne('group')
            class Meta:
                model = self.BOOK_STORE
                permissions = {
                    'read': ['admin','group:group'],
                    'create': 'admin'
                }

        class BookResource(PrincipalResource):
            store = fields.ToOne('book_store')
            group = fields.ToOne('group')
            class Meta:
                model = self.BOOK
                permissions = {
                    'read': ['admin','read:store'],
                    'create': 'admin'
                }

        class UserResource(PrincipalResource):
            group = fields.ToOne('group')
            class Meta:
                model = self.USER
                permissions = {
                    'read' : 'admin',
                    'create' : 'admin'
                }


        self.api.add_resource(GroupResource)
        self.api.add_resource(BookStoreResource)
        self.api.add_resource(BookResource)
        self.api.add_resource(UserResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.assert200(self.client.post('/group', data=[
            {'name': 'Group 1'},
            {'name': 'Group 2'},
            {'name': 'Group 3'},
            {'name': 'Group 4'}
        ]))
        self.assert200(self.client.post('/user', data=[
            {'name': 'Admin'},
            {'name': 'Author 1', 'group': '/group/2'},
            {'name': 'Author 2', 'group': '/group/2'},
            {'name': 'Author 3', 'group': '/group/3'}
        ]))
        self.assert200(self.client.post('/book_store', data=[
            {'name': 'Store 1', 'group': '/group/2'},
            {'name': 'Store 2', 'group': '/group/2'},
            {'name': 'Store 3', 'group': '/group/3'},
            {'name': 'Store 4', 'group': '/group/4'},
        ]))
        self.assert200(self.client.post('/book', data=[
            {'store': '/book_store/1', 'title': 'Book 2.1.1'}, # group #2
            {'store': '/book_store/1', 'title': 'Book 2.1.2'}, # group #2
            {'store': '/book_store/2', 'title': 'Book 2.2.1'}, # group #2
            {'store': '/book_store/2', 'title': 'Book 2.2.2'}, # group #2
            {'store': '/book_store/2', 'title': 'Book 2.2.3'}, # group #2
            {'store': '/book_store/2', 'title': 'Book 2.2.4'}, # group #2
            {'store': '/book_store/3', 'title': 'Book 3.3.1'}, # group #3
            {'store': '/book_store/3', 'title': 'Book 3.3.2'}, # group #3
            {'store': '/book_store/4', 'title': 'Book 4.4.1'}, # group #4
            {'store': '/book_store/4', 'title': 'Book 4.4.2'}, # group #4
        ]))
        response = self.client.get('/book')
        self.assert200(response)
        self.assertEqual(10, len(response.json))

        self.mock_user = {'id': 1, 'roles': ['group'], 'needs': [ItemNeed('group', 1, 'group')]}
        response = self.client.get('/book_store')
        self.assert200(response)
        self.assertEqual(0, len(response.json))

        self.mock_user = {'id': 2, 'roles': ['group'], 'needs': [ItemNeed('group', 2, 'group')]}
        response = self.client.get('/book_store')
        self.assert200(response)
        self.assertEqual(2, len(response.json))

        self.mock_user = {'id': 3, 'roles': ['group'], 'needs': [ItemNeed('group', 2, 'group')]}
        response = self.client.get('/book_store')
        self.assert200(response)
        self.assertEqual(2, len(response.json))

        self.mock_user = {'id': 4, 'roles': ['group'], 'needs': [ItemNeed('group', 3, 'group')]}
        response = self.client.get('/book_store')
        self.assert200(response)
        self.assertEqual(1, len(response.json))

        #

        self.mock_user = {'id': 1, 'roles': ['admin']}
        response = self.client.get('/book')
        self.assert200(response)
        self.assertEqual(10, len(response.json))

        self.mock_user = {'id': 2, 'roles': ['group'], 'needs': [ItemNeed('group', 2, 'group')]}
        response = self.client.get('/book')
        self.assert200(response)
        self.assertEqual(6, len(response.json))

        self.mock_user = {'id': 3, 'roles': ['group'], 'needs': [ItemNeed('group', 2, 'group')]}
        response = self.client.get('/book')
        self.assert200(response)
        self.assertEqual(6, len(response.json))

        self.mock_user = {'id': 4, 'roles': ['group'], 'needs': [ItemNeed('group', 3, 'group')]}
        response = self.client.get('/book')
        self.assert200(response)
        self.assertEqual(2, len(response.json))

        self.mock_user = {'id': 5, 'roles': ['group'], 'needs': [ItemNeed('group', 4, 'group')]}
        response = self.client.get('/book')
        self.assert200(response)
        self.assertEqual(2, len(response.json))


    def test_relationship(self):
        "should require update permission on parent resource for updating, read permissions on both"

        class BookResource(PrincipalResource):
            author = fields.ToOne('user')

            class Meta:
                model = self.BOOK
                permissions = {
                    'read': ['owns-copy', 'update'],
                    'create': 'writer',
                    'update': 'user:author',
                    'owns-copy': 'owns-copy'
                }

        class UserResource(PrincipalResource):
            books = Relationship(BookResource)

            class Meta:
                model = self.USER
                permissions = {
                    'create': 'admin'
                }

        self.api.add_resource(UserResource)
        self.api.add_resource(BookResource)

        self.mock_user = {'id': 1, 'roles': ['admin']}
        self.client.post('/user', data=[
            {'title': 'Admin'},
            {'title': 'Author 1'},
            {'title': 'Author 2'}
        ])

        response = self.client.post('/user/1/books', data={
            'title': 'Foo'
        })

        self.assert403(response)

        self.mock_user = {'id': 2, 'roles': ['writer']}
        response = self.client.post('/book', data={
            'author': '/user/2',
            'title': 'Bar'
        })

        self.assert200(response)

        self.mock_user = {'id': 3, 'roles': ['writer']}
        response = self.client.post('/user/3/books', data=[
            {'title': 'Spying: Novel'},
            {'title': 'Spied: Sequel'},
            {'title': 'Spy: Prequel'}
        ])

        self.assert200(response)

        response = self.client.get('/user/3/books')
        self.assert200(response)
        self.assertEqual(3, len(response.json))  # read -> update -> user:author

        self.mock_user = {'id': 4, 'needs': [ItemNeed('owns-copy', 3, 'book')]}
        response = self.client.get('/user/3/books')
        self.assertEqual(1, len(response.json))  # read -> owns-copy

        self.assert200(self.client.get('/book/3'))
        self.assert404(self.client.get('/book/2'))

        self.mock_user = {'id': 5}
        response = self.client.get('/user/3/books')
        self.assertEqual(0, len(response.json))
        self.assert404(self.client.get('/book/2'))


    @unittest.SkipTest
    def test_item_action(self):
        "should require read permission on parent resource plus any additional permissions"
        pass

    def test_permission_circular(self):
        class BookResource(PrincipalResource):
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
