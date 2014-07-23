
Advanced Recipes
================


Inline Models
-------------

Sometimes SQLAlchemy model are so intrinsically linked to a parent model that it makes no sense to create a separate
resource route for them. They're always accessed as part of the parent document.
To inline a model, simply create a field class like this one:

.. code-block:: python

    class InlineModel(fields.Nested):
        def __init__(self, fields, model, **kwargs):
            super().__init__(fields, **kwargs)
            self.model = model

        def convert(self, obj):
            obj = EmbeddedJob.complete(super().convert(obj))
            if obj is not None:
                obj = self.model(**obj)
            return obj

        def format(self, obj):
            return marshal(obj, self.fields)


Example usage
^^^^^^^^^^^^^

.. code-block:: python

    class UserResource(ModelResource):
        addresses = fields.List(InlineModel({
            'address_1': fields.String(),
            'address_2': fields.String(),
            'city': fields.String(),
            'post_code': fields.String()
        }, model=UserAddress))

        class Meta:
            model = User


Remember to set cascade to ``all, delete-orphan`` on the backref from the child model.

There is an open SQLAlchemy 0.9 issue `#2501 <https://bitbucket.org/zzzeek/sqlalchemy/issue/2501>`_ regarding unique
key integrity errors when items in a relationship are overwritten. The solution is to flush the session before the
new items are added. If you have unique constraints in your child model you can use the following workaround:

::

    @signals.before_update_item.connect_via(UserResource)
    def before_update_item(signal, item, changes, partial):
        if 'addresses' in changes:  # manually delete all the old addresses:
            item.addresses = []
            object_session(item).flush()


..

    Attribute Mapped Collections
    ----------------------------




Polymorphic Models
------------------

Support for polymorphic models has been removed from Flask-Presst as it was seen to be out of scope. However, the
functionality can be brought back in with the following recipe:

.. code-block:: python

    class PolymorphicApi(PresstApi):

        def __init__(self, *args, **kwargs)
            super().__init__(*args, **kwargs)
            self._model_resources = {}

        def add_resource(self, resource, *urls, **kwargs):
            if isinstance(resource, ModelResource):
                self._model_resources[resource._model] = resource

            super().add_resource(resource, *urls, **kwargs)

.. code-block:: python


    class PolymorphicModelResource(ModelResource):
        """
        :class:`PolymorphicModelResource` is identical to :class:`ModelResource`, except that when it marshals an item
        that has a different class than the ``model`` attribute defined in :class:`Meta`, it marshals the contents of that
        model separately from the inherited resource and adds it to the marshalled dictionary as a property with the
        name of the inherited resource.

        e.g.

        .. code-block:: javascript

            {
                "_uri": "/polymorphic_resource/1",
                // polymorphic_resource properties
                "base_resource": {
                    "_uri": "/base_resource/1",
                    // base_resource properties
                }
            }


        :class:`PolymorphicModelResource` is designed to be used with SQLAlchemy models that
        make use of `SQLAlchemy's polymorphic inheritance <http://docs.sqlalchemy.org/en/latest/orm/inheritance.html>`_.
        """

        @classmethod
        def marshal_item(cls, item):
            resource = cls.api._model_resources[item.__class__]
            marshaled = super(PolymorphicModelResource, cls).marshal_item(item)

            if resource and resource != cls:
                marshaled[resource.resource_name.replace('/', '__')] = resource.marshal_item(item)

            # fallback:
            return marshaled