import json
import unittest
from flask import Flask
from flask.ext.restful import abort
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
        return (cls.get_item_for_id(id) for id in parent_item[relationship])

    @classmethod
    def create_item_relationship(cls, id_, relationship, parent_item):
        raise NotImplementedError()

    @classmethod
    def delete_item_relationship(cls, id_, relationship, parent_item):
        raise NotImplementedError()

    @classmethod
    def create_item(cls, dct):
        """This method must either return the created item or abort with the appropriate error."""
        item_id = len(cls.items) + 1
        dct.update(item_id)
        cls.items.append(dct)
        return dct

    @classmethod
    def update_item(cls, id_, dct, is_partial=False):
        "This method must either return the updated item or abort with the appropriate error."
        item = cls.get_item_for_id(id_)
        item.update(dct)
        return dct

    @classmethod
    def delete_item(cls, id_):
        try:
            del cls.items[id_]
        except KeyError:
            abort(404)
        return None, 204


class PresstTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app = Flask(__name__)

        app.testing = True

        self.api = PresstApi(app)

    def tearDown(self):
        pass

    def request(self, method, url, data, *result):
        with self.app.test_client() as client:
            self.assertEqual(
                self.parse_response(
                    getattr(client, method.lower())(url, data=json.dumps(data), content_type='application/json')),
                result)

    def parse_response(self, r):
        v = json.loads(r.data.decode()) if r.status_code == 200 else None
        return v, r.status_code