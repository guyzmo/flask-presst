import json
import unittest
from flask import Flask
from flask_restful import abort
from flask_testing import TestCase
from flask.testing import FlaskClient
import six
from flask_presst import Resource, PresstApi


class SimpleResource(Resource):
    items = []

    @classmethod
    def get_item_for_id(cls, id_):
        for item in cls.items:
            if item['id'] == id_:
                return item
        abort(404)

    @classmethod
    def get_item_list(cls, where=None):
        return cls.items

    @classmethod
    def get_relationship(cls, item, relationship):
        child_resource = cls.routes[relationship].resource
        return (child_resource.get_item_for_id(id_) for id_ in item[relationship])

    @classmethod
    def add_to_relationship(cls, item, relationship, child):
        child_resource = cls.routes[relationship].resource
        item[relationship].append(child_resource.item_get_id(child))
        return child

    @classmethod
    def remove_from_relationship(cls, item, relationship, child):
        child_resource = cls.routes[relationship].resource
        item[relationship].remove(child_resource.item_get_id(child))

    @classmethod
    def create_item(cls, properties, commit=False):
        """This method must either return the created item or abort with the appropriate error."""
        item_id = len(cls.items) + 1
        properties.update({'id': item_id})
        cls.items.append(properties)
        return properties

    @classmethod
    def update_item(cls, item, changes, partial=False, commit=False):
        "This method must either return the updated item or abort with the appropriate error."
        item.update(changes)
        return item

    @classmethod
    def delete_item(cls, item):
        try:
            del cls.items[cls.item_get_id(item)]
        except KeyError:
            abort(404)
        return None, 204


class ApiClient(FlaskClient):
    def open(self, *args, **kw):
        """
        Sends HTTP Authorization header with  the ``HTTP_AUTHORIZATION`` config value
        unless :param:`authorize` is ``False``.
        """
        headers = kw.pop('headers', [])

        if 'data' in kw and (kw.pop('force_json', False) or not isinstance(kw['data'], str)):
            kw['data'] = json.dumps(kw['data'])
            kw['content_type'] = 'application/json'

        return super(ApiClient, self).open(*args, headers=headers, **kw)

class PresstTestCase(TestCase):
    def create_app(self):
        app = Flask(__name__)
        app.secret_key = 'secret'
        app.test_client_class = ApiClient
        app.config['TESTING'] = True
        return app

    def setUp(self):
        self.api = PresstApi(self.app)

    def tearDown(self):
        pass

    def _without(self, dct, without):
        return {k: v for k, v in dct.items() if k not in without}

    def assertEqualWithout(self, first, second, without, msg=None):
        if isinstance(first, list) and isinstance(second, list):
            self.assertEqual(
                [self._without(v, without) for v in first],
                [self._without(v, without) for v in second],
                msg=msg
            )
        elif isinstance(first, dict) and self.assertEqual(second, dict):
            self.assertEqual(self._without(first, without),
                             self._without(second, without),
                             msg=msg)
        else:
            self.assertEqual(first, second)

    def request(self, method, url, data, *result):
        with self.app.test_client() as client:
            self.assertEqual(
                result,
                self.parse_response(
                    getattr(client, method.lower())(url, data=json.dumps(data), content_type='application/json')))

    def parse_response(self, r):
        v = json.loads(r.data.decode()) if r.status_code == 200 else None
        return v, r.status_code