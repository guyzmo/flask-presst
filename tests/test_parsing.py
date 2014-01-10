from datetime import datetime
from flask.ext.restful import reqparse
from pytz import UTC
from flask.ext.presst import PresstArgument, fields
from tests import PresstTestCase


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
                '&none=None'
                '&int=-1'):
            self.assertEqual(parser.parse_args(),
                             {'date': datetime(2014, 1, 10, 12, 18, tzinfo=UTC),
                              'int': -1,
                              'none': 'None',
                              'text': 'text'})

    def test_parsing_fields(self):
        parser = reqparse.RequestParser(argument_class=PresstArgument)
        parser.add_argument('date', type=fields.DateTime())
        parser.add_argument('none', type=fields.String())
        parser.add_argument('text', type=fields.String())
        parser.add_argument('int', type=fields.Integer())
        # NOTE reference fields are tested elsewhere.

        with self.app.test_request_context(
                '/?date=2014-01-10T12:18Z'
                '&text=text'
                '&none=None'
                '&int=-1'):
            self.assertEqual(parser.parse_args(),
                             {'date': datetime(2014, 1, 10, 12, 18, tzinfo=UTC),
                              'int': -1,
                              'none': 'None',
                              'text': 'text'})
