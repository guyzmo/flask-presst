from importlib import import_module
import inspect

from flask import current_app, request
from flask_restful import Resource, abort
import six


class ResourceRef(object):
    def __init__(self, reference):
        self.reference_str = reference

    def resolve(self):
        """
        Resolve attempts three different methods for resolving a reference:

        - if the reference is a Resource, return it
        - if the reference is a Resource name in the current_app.unrest API context, return it
        - if the reference is a complete module.class string, import and return it
        """
        r = self.reference_str

        if inspect.isclass(r) and issubclass(r, Resource):
            return r

        if hasattr(current_app, 'presst'):
            return current_app.presst.get_resource_class(r)

        try:
            if isinstance(r, six.string_types):
                module_name, class_name = r.rsplit('.', 1)
                module = import_module(module_name)
                return getattr(module, class_name)
        except ValueError:
            pass

        raise RuntimeError('Could not resolve resource reference: {}'.format(r))

    def __repr__(self):
        return "<ResourceRef '{}'>".format(self.resolve().resource_name)


class EmbeddedJob(object):
    def __init__(self, resource, data, item=None, **kwargs):
        self.resource = resource
        self.item = item
        self.data = data
        self.kwargs = kwargs

    def __call__(self):
        if self.item:
            return self.resource.update_item(self.item, EmbeddedJob.complete(self.data), **self.kwargs)
        else:
            return self.resource.create_item(EmbeddedJob.complete(self.data), **self.kwargs)

    @classmethod
    def complete(cls, obj):
        if isinstance(obj, EmbeddedJob):
            return obj()
        elif isinstance(obj, dict):
            return {k: EmbeddedJob.complete(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [EmbeddedJob.complete(i) for i in obj]
        else:
            return obj

def resolve_item(resource, data, read=True, create=False, update=False, commit=True, resolved_properties=None, parse_only=False):
    if (create or update) and request.method not in ('POST', 'PUT', 'PATCH'):
        create = update = False

    if read and isinstance(data, six.text_type):
        return resource.get_item_from_uri(data)
    elif isinstance(data, dict):
        item = None
        # if '_id' in data:
        #     item = cls.get_item_for_id(data.pop('_id'))
        if read and '_uri' in data:
            item = resource.get_item_from_uri(data.pop('_uri'))
        if item:
            if update and data:
                item_changes = resource.item_parser.parse(data, resolve=resolved_properties, partial=True)
                return EmbeddedJob(resource, item_changes, item=item, commit=commit)
            return item
        elif not create:
            abort(400, message='Resource URI missing in JSON dictionary')
        else:
            item_data = resource.item_parser.parse(data, resolve=resolved_properties)
            return EmbeddedJob(resource, item_data, commit=commit)
    elif read:
        abort(400, message='JSON string or dictionary required')
    else:
        abort(400, message='JSON dictionary required')


class ItemWrapper(object):
    def __init__(self, resource, item):
        self.resource = resource
        self.item = item

    @classmethod
    def read(cls, resource, id):
        return ItemWrapper(resource, resource.get_item_for_id(id))

    @classmethod
    def resolve(cls, resource, properties, many=False, commit=True, **kwargs):
        if not isinstance(properties, (dict, six.text_type)):
            abort(400, message='JSON dictionary or string required')

        item = resolve_item(resource, properties, commit=commit, **kwargs)
        return ItemWrapper(resource, item)

    @classmethod
    def create(cls, resource, properties, resolved_properties=None, commit=True):
        return EmbeddedJob.complete(cls.resolve(resource,
                                                properties,
                                                resolved_properties=resolved_properties,
                                                read=False,
                                                create=True,
                                                commit=commit))

    def update(self, changes, resolved_properties=None, partial=False, commit=True):
        item_changes = self.resource.item_parser.parse(changes, resolve=resolved_properties, partial=partial)
        self.item = self.resource.update_item(self.item, EmbeddedJob.complete(item_changes), commit=commit, partial=partial)
        return self

    def get_relationship(self, relationship, target_resource):
        return ItemListWrapper(target_resource, self.resource.get_relationship(self.item, relationship))

    def add_to_relationship(self, relationship, wrapped_items, commit=True):
        if isinstance(wrapped_items, ItemListWrapper):
            child_items = [self.resource.add_to_relationship(self.item, relationship, child)
                           for child in wrapped_items.items]
            if commit:
                self.resource.commit()

            return ItemListWrapper(wrapped_items.resource, child_items)
        elif isinstance(wrapped_items, ItemWrapper):
            child = self.resource.add_to_relationship(self.item, relationship, wrapped_items.item)

            if commit:
                self.resource.commit()

            return ItemWrapper(wrapped_items.resource, child)
        else:
            raise NotImplementedError()

    def remove_from_relationship(self, relationship, wrapped_items, commit=True):
        if isinstance(wrapped_items, ItemListWrapper):
            for child in wrapped_items.items:
                self.resource.remove_from_relationship(self.item, relationship, child)
        elif isinstance(wrapped_items, ItemWrapper):
            self.resource.remove_from_relationship(self.item, relationship, wrapped_items.item)
        if commit:
            self.resource.commit()

    def delete(self, commit=True):
        self.resource.delete_item(self.item)

    @property
    def id(self):
        return self.resource.item_get_id(self.item)

    @property
    def uri(self):
        return self.resource.item_get_uri(self.item)

    def raw(self):
        return self.item

    def marshal(self):
        return self.resource.marshal_item(self.item)


class ItemListWrapper(object):

    def __init__(self, resource, items):
        self.resource = resource
        self.items = items

    @classmethod
    def resolve(cls, resource, properties, commit=True, **kwargs):
        if not isinstance(properties, (dict, list, six.text_type)):
            abort(400, message='JSON dictionary, string, or array required')

        if isinstance(properties, list):
            # TODO handle commit in here (commit once after list operation)
            items = [resolve_item(resource, p, commit=False, **kwargs) for p in properties]
            items = EmbeddedJob.complete(items)

            if commit:
                resource.commit()
            return ItemListWrapper(resource, items)

        item = EmbeddedJob.complete(resolve_item(resource, properties, commit=commit, **kwargs))
        return ItemWrapper(resource, item)

    @classmethod
    def get_list(cls, resource):
        return ItemListWrapper(resource, resource.get_item_list())

    @classmethod
    def create(cls, resource, properties, commit=True, **kwargs):
        return cls.resolve(resource, properties, commit=commit, read=False, create=True, **kwargs)

    def raw(self):
        return self.items

    def marshal(self):
        return self.resource.marshal_item_list(self.items)

