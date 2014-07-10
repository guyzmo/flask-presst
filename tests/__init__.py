import json
import unittest
from flask import Flask
from flask.ext.restful import abort
from flask.ext.testing import TestCase
from flask.testing import FlaskClient
import six
from flask.ext.presst import PresstResource, PresstApi


class TestPresstResource(PresstResource):
    items = []

    @classmethod
    def get_item_for_id(cls, id_):
        for item in cls.items:
            if item['id'] == id_:
                return item
        abort(404)

    @classmethod
    def get_item_list(cls):
        return cls.items

    @classmethod
    def get_item_list_for_relationship(cls, relationship, parent_item):
        return (cls.get_item_for_id(id_) for id_ in parent_item[relationship])

    @classmethod
    def create_item_relationship(cls, id_, relationship, parent_item):
        parent_item[relationship].append(id_)
        return cls.get_item_for_id(id_)

    @classmethod
    def delete_item_relationship(cls, id_, relationship, parent_item):
        parent_item[relationship].remove(id_)

    @classmethod
    def create_item(cls, dct):
        """This method must either return the created item or abort with the appropriate error."""
        item_id = len(cls.items) + 1
        dct.update({'id': item_id})
        cls.items.append(dct)
        return dct

    @classmethod
    def update_item(cls, id_, dct, partial=False):
        "This method must either return the updated item or abort with the appropriate error."
        item = cls.get_item_for_id(id_)
        item.update(dct)
        return item

    @classmethod
    def delete_item(cls, id_):
        try:
            del cls.items[id_]
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
        app.test_client_class = ApiClient
        app.config['TESTING'] = True
        return app

    def setUp(self):
        self.api = PresstApi(self.app)

    def tearDown(self):
        pass

    def request(self, method, url, data, *result):
        with self.app.test_client() as client:
            self.assertEqual(
                result,
                self.parse_response(
                    getattr(client, method.lower())(url, data=json.dumps(data), content_type='application/json')))

    def parse_response(self, r):
        v = json.loads(r.data.decode()) if r.status_code == 200 else None
        return v, r.status_code