from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask.ext.presst import fields, ModelResource, PresstApi, Relationship, resource_method
from flask.ext.presst.signals import before_create_item

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

api = PresstApi(app)

db = SQLAlchemy(app)

class Tree(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)


class Fruit(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(60), nullable=False)
    sweetness = db.Column(db.Integer)

    tree_id = db.Column(db.Integer, db.ForeignKey(Tree.id))
    tree = db.relationship(Tree, backref=backref('fruits', lazy='dynamic'))

db.create_all()


class TreeResource(ModelResource):
    fruits = Relationship('Fruit')

    class Meta:
        model = Tree

    @resource_method('GET')
    def fruit_count(self, tree):
        return tree.fruits.count()


class FruitResource(ModelResource):
    tree = fields.ToOne(TreeResource, embedded=True)

    class Meta:
        model = Fruit


@before_create_item.connect_via(FruitResource)
def before_create_fruit(sender, item):
    item.sweetness += 1  # make extra sweet

api.add_resource(FruitResource)
api.add_resource(TreeResource)
api.enable_schema()

if __name__ == '__main__':
    app.run()
