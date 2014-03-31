from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.presst import PresstApi, ModelResource

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

db = SQLAlchemy(app)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(), nullable=False)
    year_published = db.Column(db.Integer)

db.create_all()

class BookResource(ModelResource):
    class Meta:
        model = Book

api = PresstApi(app)
api.add_resource(BookResource)

if __name__ == '__main__':
    app.run()
