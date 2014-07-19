
=======
Signals
=======

Flask-Presst comes with several `Blinker <http://pythonhosted.org/blinker/>`_ signals. The signals can be used to
pre-process and post-process most parts of the read, create, update cycle.

:class:`ModelResource` and :class:`PolymorphicModelResource` instances hook into these signals; other child classes of
:class:`Resource` should be written to hook into them as well.

.. module:: flask_presst.signals


.. class:: before_create_item

    Resources will send an ``item`` keyword argument, which is a model instance of the newly created item.

    Signal listeners can edit the item:

    >>> @before_create_item.connect_via(ArticleResource)
    ... def on_before_create_article(sender, item):
    ...     item.author_id = current_user.id

    Listeners may also raise exceptions:

    >>> @before_create_item.connect_via(ArticleResource)
    ... def on_before_create_article(sender, item):
    ...     if not current_user.is_editor:
    ...         abort(400)

    :param sender: item resource
    :param item: instance of item

.. class:: after_create_item

    Resources will send an ``item`` keyword argument, which is a model instance of the newly created item.

    :param sender: item resource
    :param item: instance of item

.. class:: before_update_item

    Resources will send ``item``, ``changes`` and ``partial`` keywords arguments, where ``changes`` is a parsed
    ``dict`` of changes and ``partial`` indicates whether the changes are partial. The signal is sent before any
    of the changes have been copied.

    :param sender: item resource
    :param item: instance of item
    :param dict changes: dictionary of changes, already parsed
    :param bool partial:

.. class:: after_update_item

    Resources will send ``item``, ``changes`` and ``partial`` keywords arguments, where ``changes`` is a parsed
    ``dict`` of changes and ``partial`` indicates whether the changes are partial. The signal is sent after the
    changes have been copied and committed, so any further changes will require an additional commit within
    the listener.

    :param sender: item resource
    :param item: instance of item
    :param dict changes: dictionary of changes, already parsed
    :param bool partial:

.. class:: before_delete_item

    Resources will send an ``item`` keyword argument, which is a model instance of the item to be deleted.

    :param sender: item resource
    :param item: instance of item

.. class:: after_delete_item

    Resources will send an ``item`` keyword argument, which is a model instance of the already deleted item.

    :param sender: item resource
    :param item: instance of item

.. class:: before_add_relationship

    :param sender: parent resource
    :param item: instance of parent item
    :param relationship: name of relationship to child
    :param child: instance of child item

.. class:: after_add_relationship

    :param sender: parent resource
    :param item: instance of parent item
    :param relationship: name of relationship to child
    :param child: instance of child item

.. class:: before_remove_relationship

    :param sender: parent resource
    :param item: instance of parent item
    :param relationship: name of relationship to child
    :param child: instance of child item

.. class:: after_remove_relationship

    :param sender: parent resource
    :param item: instance of parent item
    :param relationship: name of relationship to child
    :param child: instance of child item

.. note::

    Relationship-related signals have a caveat: They only apply to relations created through collections,
    that is not through ``ToOne``, ``ToMany`` etc. fields. When a relationship is altered through a
    field, this will trigger the before/after update signals, but not before/after add/remove relationship.
