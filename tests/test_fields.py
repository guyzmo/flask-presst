from datetime import datetime
from flask_presst import fields
from tests import PresstTestCase, SimpleResource
from pytz import UTC


class TestFields(PresstTestCase):
    def setUp(self):
        super(TestFields, self).setUp()

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

    def test_import_module_name(self):
        self.assertEqual(fields.String.__module__, 'flask_restful.fields')
        self.assertEqual(fields.Date.__module__, 'flask_presst.fields')

    def test_get_date(self):
        self.request('GET', '/press/1', None,
            {'resource_uri': '/press/1',
             'last_serviced': 'Wed, 12 Feb 2014 15:08:00 -0000',
             'name': 'Press 1'}, 200)

    def test_post_read_only(self):
        response = self.client.post('/press/1', data={'name': 'Press I'})

        self.assert200(response)
        self.assertEqual({'resource_uri': '/press/1',
                          'last_serviced': 'Wed, 12 Feb 2014 15:08:00 -0000',
                          'name': 'Press I'}, response.json)

        self.request('POST', '/press/1',
            {
                'name': 'Press 1',
                'last_serviced': 'Wed, 12 Feb 2014 15:10:00 -0000'
            },
            {'resource_uri': '/press/1',
             'last_serviced': 'Wed, 12 Feb 2014 15:08:00 -0000', # read-only fields are ignored; could throw error.
             'name': 'Press 1'}, 200)
