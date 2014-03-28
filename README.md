# Flask-Presst

[![Build Status](https://travis-ci.org/biosustain/flask-presst.png)](https://travis-ci.org/biosustain/flask-presst)
[![Coverage Status](https://coveralls.io/repos/biosustain/flask-presst/badge.png?branch=master)](https://coveralls.io/r/biosustain/flask-presst?branch=master)
[![PyPI version](https://badge.fury.io/py/Flask-Presst.png)](http://badge.fury.io/py/Flask-Presst)
[![Requirements Status](https://requires.io/github/biosustain/flask-presst/requirements.png?branch=master)](https://requires.io/github/biosustain/flask-presst/requirements/?branch=master)

Flask-Presst is a Flask extension for REST APIs (that itself extends
[Flask-RESTful](https://github.com/twilio/flask-restful)) and is designed for the SQLAlchemy ORM in general and
PostgreSQL in particular.

This extension is a work in progress. It was extracted from another project recently and has not yet been fully rewritten.
The documentation is only being started on just now. In the meant time check out the test cases for guidance.

## Features

- Support for SQLAlchemy models, including:
    - PostgreSQL __JSON & HSTORE__ field types
    - Model __inheritance__
- __Embeddable resources__ & relationship fields
- __Nested resources__
- __Object-based permissions__
- __Resource & resource-item methods__
- GitHub-style __pagination__

### Planned features

- Built-in caching support
- Batch updates for nested resources
- Batch requests using `/resource/1;2;3;4/` with atomicity through nested transactions.
- Built-in `/schema` resource & resource methods for all resources in an API.
- True child resources for non-polymorphic models with foreign-key primary keys
- Namespaces


## Example code

From `examples/modelresource_example.py`:

```python
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

if __name__ == '__main__':
    app.run()
```

### Example session

#### Simple POST
```http
POST /tree HTTP/1.1
Content-Length: 21
Content-Type: application/json; charset=utf-8

{
    "name": "LemonTree"
}
```
```http
HTTP/1.0 200 OK
Content-Length: 48
Content-Type: application/json

{
    "name": "LemonTree", 
    "resource_uri": "/tree/1"
}
```

#### POST with ToOne reference
```http
POST /fruit HTTP/1.1
Content-Length: 56
Content-Type: application/json; charset=utf-8

{
    "name": "Lemon 1", 
    "sweetness": "0", 
    "tree": "/tree/1"
}
```
```http
HTTP/1.0 200 OK
Content-Length: 121
Content-Type: application/json

{
    "name": "Lemon 1", 
    "resource_uri": "/fruit/1", 
    "sweetness": 1, 
    "tree": {
        "name": "LemonTree", 
        "resource_uri": "/tree/1"
    }
}

```

#### GET from sub-collection
```http
GET /tree/1/fruits HTTP/1.1
```
```http
HTTP/1.0 200 OK
Content-Length: 123
Content-Type: application/json

[
    {
        "name": "Lemon 1", 
        "resource_uri": "/fruit/1", 
        "sweetness": 1, 
        "tree": {
            "name": "LemonTree", 
            "resource_uri": "/tree/1"
        }
    }
]
```

#### GET from a resource (item) method
```http
GET /tree/1/fruit_count HTTP/1.1
```
```http
HTTP/1.0 200 OK
Content-Length: 2
Content-Type: application/json

1
```
