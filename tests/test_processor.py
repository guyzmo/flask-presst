import inspect
import types
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask.ext.presst import fields, ModelResource, Relationship
from flask.ext.presst.processor import Processor
from tests import PresstTestCase


class TestResourceMethod(PresstTestCase):
    def setUp(self):
        super(TestResourceMethod, self).setUp()

        class LastActionProcessor(Processor):
            def __init__(self):
                self.actions = []

            @property
            def last_action(self):
                try:
                    return self.actions[-1]
                except IndexError:
                    return None

            @classmethod
            def add_method(cls, name):
                def process(self, *args):
                    self.actions.append((name,) + args)
                    return args[0]

                setattr(cls, name, process)

        for name, func in inspect.getmembers(Processor):
            if 'before_' in name or 'after_' in name:
                LastActionProcessor.add_method(name)

        self.passive = LastActionProcessor()

        app = self.app
        app.config['SQLALCHEMY_ENGINE'] = 'sqlite://'
        app.config['TESTING'] = True

        self.db = db = SQLAlchemy(app)

        class Location(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(60), nullable=False)

        class Flag(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            location_id = db.Column(db.Integer, db.ForeignKey(Location.id), nullable=False)
            location = db.relationship(Location, backref=backref('flags', lazy='dynamic', cascade='all, delete-orphan'))

        db.create_all()

        class FlagResource(ModelResource):
            location = fields.ToOne('Location', required=True)

            class Meta:
                model = Flag

        class LocationResource(ModelResource):
            name = fields.String()

            flags = Relationship(FlagResource)

            class Meta:
                model = Location
                processors = [Processor(), self.passive]

        self.LocationResource = LocationResource

        self.api.add_resource(FlagResource)
        self.api.add_resource(LocationResource)

    def test_passive(self):
        self.assertEqual(self.passive.last_action, None)

        self.request('GET', '/location', None, [], 200)
        self.assertEqual(self.passive.last_action[::2], ('filter_before_read', self.LocationResource))

        self.request('POST', '/location', {'name': 'Yard'}, {'name': 'Yard', 'resource_uri': '/location/1'}, 200)
        self.assertEqual(self.passive.actions[-3][::2], ('filter_before_read', self.LocationResource))
        self.assertEqual(self.passive.actions[-2][0], 'before_create_item')
        self.assertEqual(self.passive.actions[-1][0], 'after_create_item')

        self.request('POST', '/location/1', {'name': 'House'}, {'name': 'House', 'resource_uri': '/location/1'}, 200)
        self.assertEqual(self.passive.actions[-3][0], 'filter_before_update')
        self.assertEqual(self.passive.actions[-2][::2][0:2], ('before_update_item', {'name': 'House'}))
        self.assertEqual(self.passive.last_action[0], 'after_update_item')

        self.request('PATCH', '/location/1', {}, {'name': 'House', 'resource_uri': '/location/1'}, 200)
        self.assertEqual(self.passive.actions[-3][0], 'filter_before_update')
        self.assertEqual(self.passive.last_action[0], 'after_update_item')

        self.request('GET', '/location/1/flags', None, [], 200)
        self.request('POST', '/flag', {'location': '/location/1'},
                     {'location': '/location/1', 'resource_uri': '/flag/1'}, 200)

        self.request('DELETE', '/location/1', None, None, 204)
        self.assertEqual(self.passive.actions[-3][0], 'filter_before_delete')
        self.assertEqual(self.passive.actions[-2][0], 'before_delete_item')
        self.assertEqual(self.passive.last_action[0], 'after_delete_item')

        self.request('GET', '/location/1/flags', None, None, 404)
        self.request('GET', '/flag', None, [], 200)


    def test_filter_active(self):
        pass

    def test_relationship(self):
        pass