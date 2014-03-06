from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm import backref
from flask.ext.presst import signals, fields, ModelResource, Relationship
from flask.ext.presst.processor import Processor
from tests import PresstTestCase


class TestResourceMethod(PresstTestCase):
    def setUp(self):
        super(TestResourceMethod, self).setUp()

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

        class Recorder(object):
            def __init__(self):
                self.actions = []
                self.callbacks = {}

            @property
            def last_action(self):
                try:
                    return self.actions[-1]
                except IndexError:
                    return None

            def __call__(self, *args, **kwargs):
                self.actions.append(args + (kwargs,))

            def callback_for(self, name):
                def callback(*args, **kwargs):
                    self(name, *args, **kwargs)

                # signal listeners are a weak dictionary, therefore need to store here:
                self.callbacks[name] = callback
                return callback


        class PassiveProcessor(Processor):

            def __init__(self, recorder):
                self.recorder = recorder

            def filter_before_read(self, query, resource_class):
                self.recorder('filter_before_read', query, resource_class)
                return query

            def filter_before_update(self, query, resource_class):
                self.recorder('filter_before_update', query, resource_class)
                return query

            def filter_before_delete(self, query, resource_class):
                self.recorder('filter_before_delete', query, resource_class)
                return query

        self.recorder = record = Recorder()


        class FlagResource(ModelResource):
            location = fields.ToOne('Location', required=True)

            class Meta:
                model = Flag


        class LocationResource(ModelResource):
            name = fields.String()

            flags = Relationship(FlagResource)

            class Meta:
                model = Location
                processors = [Processor(), PassiveProcessor(record)]


        class ActiveProcessor(Processor):

            def filter_before_read(self, query, resource_class):
                return query.filter(Location.name.startswith('H'))


        class LimitedLocationResource(ModelResource):
            name = fields.String()

            class Meta:
                model = Location
                processors = [ActiveProcessor()]
                resource_name = 'limitedlocation'


        for signal in [
            signals.before_create_item,
            signals.after_create_item,
            signals.before_update_item,
            signals.after_update_item,
            signals.before_delete_item,
            signals.after_delete_item,
            signals.before_create_relationship,
            signals.after_create_relationship,
            signals.before_delete_relationship,
            signals.after_delete_relationship]:

            signal.connect(record.callback_for(signal.name.replace('-', '_')), LocationResource)

        self.LocationResource = LocationResource

        self.api.add_resource(FlagResource)
        self.api.add_resource(LocationResource)
        self.api.add_resource(LimitedLocationResource)

    def test_passive(self):
        self.assertEqual(self.recorder.last_action, None)

        self.request('GET', '/location', None, [], 200)
        self.assertEqual(self.recorder.last_action[::2], ('filter_before_read', self.LocationResource))

        self.request('POST', '/location', {'name': 'Yard'}, {'name': 'Yard', 'resource_uri': '/location/1'}, 200)
        self.assertEqual(self.recorder.actions[-3][::2], ('filter_before_read', self.LocationResource))
        self.assertEqual(self.recorder.actions[-2][0], 'before_create_item')
        self.assertEqual(self.recorder.actions[-1][0], 'after_create_item')

        self.request('POST', '/location/1', {'name': 'House'}, {'name': 'House', 'resource_uri': '/location/1'}, 200)
        self.assertEqual(self.recorder.actions[-3][0], 'filter_before_update')

        self.assertEqual(self.recorder.actions[-2][::2][0], 'before_update_item')
        self.assertEqual(self.recorder.actions[-2][::2][1]['changes'], {'name': u'House'})

        self.assertEqual(self.recorder.last_action[0], 'after_update_item')

        self.request('PATCH', '/location/1', {}, {'name': 'House', 'resource_uri': '/location/1'}, 200)
        self.assertEqual(self.recorder.actions[-3][0], 'filter_before_update')
        self.assertEqual(self.recorder.last_action[0], 'after_update_item')

        self.request('GET', '/location/1/flags', None, [], 200)
        self.request('POST', '/flag', {'location': '/location/1'},
                     {'location': '/location/1', 'resource_uri': '/flag/1'}, 200)

        self.request('DELETE', '/location/1/flags', '/flag/1', None, 204)
        self.request('GET', '/location/1/flags', None, [], 200)

        self.request('DELETE', '/location/1', None, None, 204)
        self.assertEqual(self.recorder.actions[-3][0], 'filter_before_delete')
        self.assertEqual(self.recorder.actions[-2][0], 'before_delete_item')
        self.assertEqual(self.recorder.last_action[0], 'after_delete_item')

        self.request('GET', '/location/1/flags', None, None, 404)
        self.request('GET', '/flag', None, [], 200)

    def test_filter(self):
        self.request('POST', '/location', {'name': 'Yard'}, {'name': 'Yard', 'resource_uri': '/location/1'}, 200)
        self.request('POST', '/location', {'name': 'House'}, {'name': 'House', 'resource_uri': '/location/2'}, 200)
        self.request('POST', '/location', {'name': 'Shed'}, {'name': 'Shed', 'resource_uri': '/location/3'}, 200)
        self.request('POST', '/location', {'name': 'Harbor'}, {'name': 'Harbor', 'resource_uri': '/location/4'}, 200)

        self.request('GET', '/limitedlocation', None, [
            {'name': 'House', 'resource_uri': '/limitedlocation/2'},
            {'name': 'Harbor', 'resource_uri': '/limitedlocation/4'}
        ], 200)

    def test_relationship(self):
        pass