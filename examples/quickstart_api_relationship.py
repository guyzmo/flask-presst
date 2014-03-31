from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask.ext.presst import PresstApi, ModelResource, Relationship, fields

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

db = SQLAlchemy(app)

class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(), nullable=False)
    last_name = db.Column(db.String(), nullable=False)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey(Author.id))

    title = db.Column(db.String(), nullable=False)
    year_published = db.Column(db.Integer)

    author = db.relationship(Author, backref=backref('books', lazy='dynamic'))

db.create_all()

class BookResource(ModelResource):
    author = fields.ToOne('author', embedded=True)

    class Meta:
        model = Book


class AuthorResource(ModelResource):
    books = Relationship(BookResource)

    class Meta:
        model = Author

api = PresstApi(app)
api.add_resource(BookResource)
api.add_resource(AuthorResource)

if __name__ == '__main__':
    app.run()
