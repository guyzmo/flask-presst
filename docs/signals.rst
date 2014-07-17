
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

.. class:: after_create_item

    Resources will send an ``item`` keyword argument, which is a model instance of the newly created item.

.. class:: before_update_item

    Resources will send ``item``, ``changes`` and ``partial`` keywords arguments, where ``changes`` is a parsed
    ``dict`` of changes and ``partial`` indicates whether the changes are partial. The signal is sent before any
    of the changes have been copied.

.. class:: after_update_item

    Resources will send ``item``, ``changes`` and ``partial`` keywords arguments, where ``changes`` is a parsed
    ``dict`` of changes and ``partial`` indicates whether the changes are partial. The signal is sent after the
    changes have been copied and committed, so any further changes will require an additional commit within
    the listener.

.. class:: before_delete_item

    Resources will send an ``item`` keyword argument, which is a model instance of the item to be deleted.

.. class:: after_delete_item

    Resources will send an ``item`` keyword argument, which is a model instance of the already deleted item.

.. note::

    The following signals pre-process :meth:`ModelResource.get_item_list`. If they return a callable type, the callable
    will be applied to the ``query`` object. Often it may be preferable to simply replace
    :meth:`ModelResource.get_item_list` with a custom implementation:

