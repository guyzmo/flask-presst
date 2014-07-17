from flask.signals import Namespace

__all__ = (
    'before_create_item', 'after_create_item',
    'before_update_item', 'after_update_item',
    'before_delete_item', 'after_delete_item',
    'before_add_relationship', 'after_add_relationship',
    'before_remove_relationship', 'after_remove_relationship',
)

_signals = Namespace()

before_create_item = _signals.signal('before-create-item')

after_create_item = _signals.signal('after-create-item')

before_update_item = _signals.signal('before-update-item')

after_update_item = _signals.signal('after-update-item')

before_delete_item = _signals.signal('before-delete-item')

after_delete_item = _signals.signal('after-delete-item')

before_add_relationship = _signals.signal('before-add-relationship')

after_add_relationship = _signals.signal('after-add-relationship')

before_remove_relationship = _signals.signal('before-remove-relationship')

after_remove_relationship = _signals.signal('after-remove-relationship')