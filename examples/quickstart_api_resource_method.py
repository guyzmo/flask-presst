import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask_presst import PresstApi, ModelResource, Relationship, fields, action

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

    @action('GET', collection=True)
    def published_after(self, books, year):
        return BookResource.marshal_item_list(
            books.filter(Book.year_published > year))

    published_after.add_argument('year', location='args', type=int, required=True)

    @action('GET')
    def is_recent(self, item):
        return datetime.date.today().year <= item.year_published + 10

    class Meta:
        model = Book


class AuthorResource(ModelResource):
    books = Relationship(BookResource)

    class Meta:
        model = Author


api = PresstApi(app)
api.add_resource(BookResource)
api.add_resource(AuthorResource)
api.enable_schema()

if __name__ == '__main__':
    app.run()
