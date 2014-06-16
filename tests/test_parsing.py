from datetime import datetime
import json
from flask.ext.restful import reqparse
from pytz import UTC
from werkzeug.exceptions import HTTPException
from flask.ext.presst import PresstArgument, fields
from tests import PresstTestCase, TestPresstResource


class ParsingTest(PresstTestCase):
    def test_parsing_types(self):
        parser = reqparse.RequestParser(argument_class=PresstArgument)
        parser.add_argument('date', type=datetime)
        parser.add_argument('none', type=str)
        parser.add_argument('text', type=str)
        parser.add_argument('int', type=int)

        with self.app.test_request_context(
                '/?date=2014-01-10T12:18Z'
                '&text=text'
                '&int=-1', data={'none': None}):  # FIXME TODO  json to test None.
            self.assertEqual(parser.parse_args(),
                             {'date': datetime(2014, 1, 10, 12, 18, tzinfo=UTC),
                              'int': -1,
                              'none': None,
                              'text': 'text'})

    def test_parsing_fields(self):
        parser = reqparse.RequestParser(argument_class=PresstArgument)
        parser.add_argument('date_rfc', type=fields.DateTime())
        parser.add_argument('date', type=fields.DateTime())
        parser.add_argument('none', type=fields.String())
        parser.add_argument('text', type=fields.String())
        parser.add_argument('json', type=fields.JSON())
        parser.add_argument('int', type=fields.Integer())
        # NOTE reference fields are tested elsewhere.

        with self.app.test_request_context('/',
                                           data=json.dumps({
                                               'date_rfc': 'Wed, 02 Oct 2002 08:00:00 GMT',
                                               'date': '2014-01-10T12:18Z',
                                               'int': -1,
                                               'text': 'text',
                                               'none': None,
                                               'json': [1, {'a': 2}]}),
                                           content_type='application/json'):
            self.assertEqual(parser.parse_args(),
                             {
                                 'date_rfc': datetime(2002, 10, 2, 8, 0, tzinfo=UTC),
                                 'date': datetime(2014, 1, 10, 12, 18, tzinfo=UTC),
                                 'int': -1,
                                 'json': [1, {'a': 2}],
                                 'none': None,
                                 'text': 'text'})


    def test_parse_json_schema(self):
        parser = reqparse.RequestParser(argument_class=PresstArgument)
        parser.add_argument('arg', type=fields.JSON(schema={
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'value': {'type': ['integer', 'null']}
            }
        }))

        for value in [None, 1, 3, 5]:
            with self.app.test_request_context('/',
                                               data=json.dumps({
                                                   'arg': {
                                                       'name': 'test',
                                                       'value': value
                                                   }
                                               }),
                                               content_type='application/json'):
                self.assertEqual(parser.parse_args(), {'arg': {'name': 'test', 'value': value}})

        with self.app.test_request_context('/',
                                           data=json.dumps({
                                               'arg': {
                                                   'name': 'test',
                                                   'value': 'x'
                                               }
                                           }),
                                           content_type='application/json'):
            with self.assertRaises(HTTPException):
                parser.parse_args()

    def test_parse_resource_field(self):
        class PressResource(TestPresstResource):
            items = [{'id': 1, 'name': 'Press 1'}]

            name = fields.String()

            class Meta:
                resource_name = 'press'

        self.api.add_resource(PressResource)

        parser = reqparse.RequestParser(argument_class=PresstArgument)

        parser.add_argument('press', type=fields.ToOne('press'))

        # app context required to look up resource
        with self.assertRaises(RuntimeError):
            fields.ToOne('press').python_type

        with self.app.test_request_context('/',
                                           data=json.dumps({'press': '/press/1'}),
                                           content_type='application/json'):
            self.assertEqual({'press': {'id': 1, 'name': 'Press 1'}}, parser.parse_args())