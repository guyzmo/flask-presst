# Flask-Presst

Flask-Presst is a Flask extension for REST APIs (that itself extends
[Flask-RESTful](https://github.com/twilio/flask-restful)) and is designed for the SQLAlchemy ORM in general and
PostgreSQL in particular.

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

