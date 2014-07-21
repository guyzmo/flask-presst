from datetime import datetime
import json
from unittest import SkipTest
from flask import request
from pytz import UTC
from werkzeug.exceptions import HTTPException
from flask_presst import fields
from flask_presst.parse import SchemaParser
from tests import PresstTestCase, SimpleResource


class ParsingTest(PresstTestCase):

    def test_parsing_fields(self):
        parser = SchemaParser()
        parser.add('date_null', field=fields.DateTime())
        parser.add('date', field=fields.DateTime())
        parser.add('none', field=fields.String())
        parser.add('text', field=fields.String())
        parser.add('json', field=fields.JSON())
        parser.add('number', field=fields.Number())
        parser.add('int', field=fields.Integer())
        # NOTE reference fields are tested elsewhere.

        with self.app.test_request_context('/',
                                           data=json.dumps({
                                               'date_null': None,
                                               'date': '2014-01-10T12:18Z',
                                               'int': -1,
                                               'text': 'text',
                                               'none': None,
                                               'number': 12.34,
                                               'json': [1, {'a': 2}]}),
                                           content_type='application/json'):
            self.assertEqual(parser.parse_request(),
                             {
                                 'date_null': None,
                                 'date': datetime(2014, 1, 10, 12, 18, tzinfo=UTC),
                                 'int': -1,
                                 'json': [1, {'a': 2}],
                                 'none': None,
                                 'number': 12.34,
                                 'text': 'text'})

    def test_field_custom(self):
        insanity_field = fields.Custom({
                                           'type': 'object',
                                           'properties': {
                                               'a': {'type': 'integer'},
                                               'b': {'type': 'integer'}
                                           }
                                       },
                                       converter=lambda v: v['a'] + v['b'],
                                       formatter=lambda v: {'a': int(v) / 2 - 1, 'b': int(v) / 2 + 1}
        )


        self.assertEqual(5, insanity_field.parse({'a': 2, 'b': 3}))

        with self.assertRaises(ValueError):
            insanity_field.parse({'a': 2, 'b': 3.5})

        self.assertEqual({'a': 4, 'b': 6}, insanity_field.format(10))

    def test_parse_json_schema(self):
        parser = SchemaParser({'arg': fields.Raw(schema={
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'value': {'type': ['integer', 'null']}
            }
        })})

        for value in [None, 1, 3, 5]:
            with self.app.test_request_context('/',
                                               data=json.dumps({
                                                   'arg': {
                                                       'name': 'test',
                                                       'value': value
                                                   }
                                               }),
                                               content_type='application/json'):

                self.assertEqual(request.json, {'arg': {'name': 'test', 'value': value}})
                self.assertEqual(parser.parse_request(), {'arg': {'name': 'test', 'value': value}})

        with self.app.test_request_context('/',
                                           data=json.dumps({
                                               'arg': {
                                                   'name': 'test',
                                                   'value': 'x'
                                               }
                                           }),
                                           content_type='application/json'):
            with self.assertRaises(HTTPException):
                parser.parse_request()

    def test_parse_resource_field(self):
        class PressResource(SimpleResource):
            items = [{'id': 1, 'name': 'Press 1'}]

            name = fields.String()

            class Meta:
                resource_name = 'press'

        self.api.add_resource(PressResource)

        parser = SchemaParser()
        parser.add('press', fields.ToOne('press'))

        with self.app.test_request_context('/',
                                           data=json.dumps({'press': '/press/1'}),
                                           content_type='application/json'):
            self.assertEqual({'press': {'id': 1, 'name': 'Press 1'}}, parser.parse_request())