from datetime import datetime
import json
from flask.ext.restful import reqparse
from pytz import UTC
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
                '&int=-1', data={'none': None}): # FIXME TODO  json to test None.
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