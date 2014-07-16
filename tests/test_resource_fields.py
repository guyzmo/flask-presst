from datetime import datetime
from flask_presst import fields
from tests import PresstTestCase, SimpleResource
from pytz import UTC


class TestResourceFields(PresstTestCase):
    def setUp(self):
        super(TestResourceFields, self).setUp()

        class PressResource(SimpleResource):
            items = [
                {
                    'id': 1,
                    'name': 'Press 1',
                    'last_serviced': datetime(2014, 2, 12, 15, 8, tzinfo=UTC)
                }
            ]

            name = fields.String()
            last_serviced = fields.DateTime()

            class Meta:
                resource_name = 'press'
                required_fields = ['name']
                read_only_fields = ['last_serviced']

        self.api.add_resource(PressResource)

    def test_get_date(self):
        self.request('GET', '/press/1', None,
            {'_uri': '/press/1',
             'last_serviced': '2014-02-12T15:08:00+00:00Z',
             'name': 'Press 1'}, 200)

    def test_post_read_only(self):
        response = self.client.post('/press/1', data={'name': 'Press I'})

        self.assert200(response)
        self.assertEqual({'_uri': '/press/1',
                          'last_serviced': '2014-02-12T15:08:00+00:00Z',
                          'name': 'Press I'}, response.json)

        self.request('POST', '/press/1',
            {
                'name': 'Press 1',
                'last_serviced': '2014-02-12T15:10:00+00:00Z'
            },
            {'_uri': '/press/1',
             'last_serviced': '2014-02-12T15:08:00+00:00Z', # read-only fields are ignored; could throw error.
             'name': 'Press 1'}, 200)
