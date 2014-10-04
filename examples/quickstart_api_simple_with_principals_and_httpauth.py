#!bin/python

from base64 import b64decode

from flask import Flask, current_app, request
from flask_sqlalchemy import SQLAlchemy
from flask_restful import abort
from flask_presst import PresstApi, ModelResource
from flask_presst.principal import PrincipalResource
from flask.ext.principal import UserNeed, RoleNeed

#########
# Flask

app = Flask(__name__)
app.config.update(dict(
    SQLALCHEMY_DATABASE_URI = 'sqlite://',
    SECRET_KEY="super secret"
))


class User:
    def __init__(self, id):
        self.id = id
        self.roles = [id]

    def get_password(self):
        return self.id

    def __repr__(self):
        return "User<{}>".format(self.id)

#########
# Principals

from flask.ext.principal import Principal, Identity, AnonymousIdentity, identity_changed, identity_loaded

principals = Principal(app)

from functools import wraps

def authenticate(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if request.authorization:
            # Get username and password from HTTP Auth
            username, password = request.authorization.username, request.authorization.password
            # create user (or get it from a datastore)
            user = User(username)
            # check password
            if password == user.get_password():
                # create identity and assign roles
                identity = Identity(user.id)
                for role in user.roles:
                    identity.provides.add(RoleNeed(role))
                identity.provides.add(UserNeed(user.id))
                # send the changed identity
                identity_changed.send(current_app._get_current_object(), identity=identity)
                return func(*args, **kwargs)
            else:
                abort(401, message="Unauthorized: Incorrect username or password")
        else:
            abort(403, message="Permission denied: Missing credentials")
    return wrapper


#########
# Model

db = SQLAlchemy(app)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(), nullable=False)
    year_published = db.Column(db.Integer)

db.create_all()

#########
# Resource

class BookResource(PrincipalResource):
    class Meta:
        model = Book
        permissions = {
            'read': ['lambda','admin'],
            'create': 'admin',
            'update': 'admin',
            'delete': 'admin'
        }

api = PresstApi(app)

api.decorators = [authenticate]

api.add_resource(BookResource)

if __name__ == '__main__':
    app.run()

