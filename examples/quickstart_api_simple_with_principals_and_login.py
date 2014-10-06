#!bin/python

from base64 import b64decode

from flask import Flask, current_app, request, render_template, redirect, session
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

#########
# Form

from flask.ext.wtf import Form
from wtforms import TextField, PasswordField

class LoginForm(Form):
    userid = TextField()
    password = PasswordField()

#########
# Login

from flask.ext.login import LoginManager, login_user, logout_user, \
     login_required, current_user, UserMixin

login_manager = LoginManager(app)

class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.roles = [id]

    def get_password(self):
        return self.id

    def __repr__(self):
        return "User<{}>".format(self.id)

@login_manager.user_loader
def load_user(userid):
    # Return an instance of the User model
    return User(id=userid)

@login_manager.request_loader
def load_user_from_request(request):
    # Try to login using Basic Auth
    # http://flask.pocoo.org/snippets/8/
    auth = request.authorization

    if auth:
        user = User(auth.username) # XXX consider that this user may not exist
        if auth.password == user.get_password():
            return user

    # return None if no user was authenticated
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    # A hypothetical login form that uses Flask-WTF
    form = LoginForm()

    # Validate form input
    if form.validate_on_submit():
        # Retrieve the user from the hypothetical datastore
        user = User(id=form.userid.data)

        # Compare passwords (use password hashing production)
        if form.password.data == user.get_password():
            # Keep the user info in the session using Flask-Login
            login_user(user)

            # Tell Flask-Principal the identity changed
            identity_changed.send(current_app._get_current_object(),
                                  identity=Identity(user.id))

            return redirect(request.args.get('next') or '/')

    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    # Remove the user information from the session
    logout_user()

    # Remove session keys set by Flask-Principal
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    # Tell Flask-Principal the user is anonymous
    identity_changed.send(current_app._get_current_object(),
                          identity=AnonymousIdentity())

    return redirect(request.args.get('next') or '/')


#########
# Principals

from flask.ext.principal import Principal, Identity, AnonymousIdentity, identity_changed, identity_loaded

principals = Principal(app)

@principals.identity_loader
def read_identity_from_flask_login():
    if current_user.is_authenticated():
        return Identity(current_user.id)
    return AnonymousIdentity()

@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    # Set the identity user object
    identity.user = current_user

    # Add the UserNeed to the identity
    if hasattr(current_user, 'id'):
        identity.provides.add(UserNeed(current_user.id))

    # Assuming the User model has a list of roles, update the
    # identity with the roles that the user provides
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            identity.provides.add(RoleNeed(role))

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

api.decorators = [login_required]

api.add_resource(BookResource)

if __name__ == '__main__':
    app.run()

