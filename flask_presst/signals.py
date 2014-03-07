from flask.signals import Namespace

__all__ = (
    'before_create_item', 'after_create_item',
    'before_update_item', 'after_update_item',
    'before_delete_item', 'after_delete_item',
    'before_create_relationship', 'after_create_relationship',
    'before_delete_relationship', 'after_delete_relationship',
    # TODO before_create_child/after_create_child.
)

_signals = Namespace()

before_create_item = _signals.signal('before-create-item')

after_create_item = _signals.signal('after-create-item')

before_update_item = _signals.signal('before-update-item')

after_update_item = _signals.signal('after-update-item')

before_delete_item = _signals.signal('before-delete-item')

after_delete_item = _signals.signal('after-delete-item')

before_create_relationship = _signals.signal('before-create-relationship')

after_create_relationship = _signals.signal('after-create-relationship')

before_delete_relationship = _signals.signal('before-delete-relationship')

after_delete_relationship = _signals.signal('after-delete-relationship')

on_filter_read = _signals.signal('filter-read')

on_filter_update = _signals.signal('filter-update')

on_filter_delete = _signals.signal('filter-delete')