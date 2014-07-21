
================================
Object- & Role-based Permissions
================================

.. module:: flask_presst.principal

Flask-Presst ships with a permission system. The permissions system is
built on `Flask-Principal <https://pythonhosted.org/Flask-Principal/>`_
and available from :class:`PrincipalResource`, which extends :class:`ModelResource`. Permissions are defined as
a dictionary in ``Meta.permissions``.


Those who have worked with Flask-Principal know that it is not
well-suited for object-based permissions where large numbers of objects are involved, because each permission has
to be loaded into memory as ``ItemNeed`` at the start of the session. The permission system built
into Flask-Presst solves the issue by introducing :class:`HybridNeed` and :class:`HybridPermission`. They
can both be evaluated directly and modify SQLAlchemy queries.

Defining Permissions
====================

There are four basic *methods* --- read, create, update, delete --- for which permissions must be defined. (Additional
*methods* can be declared for various purposes).

For example, the default permission declaration looks somewhat like this:

.. code-block:: python

    class PrincipalResource:
        class Meta:
            permissions = {
                'read': 'yes',
                'create': 'no',
                'update': 'create',
                'delete': 'update'
            }


Patterns and *Needs* they produce:

================== ===================================== ===================================================
Pattern            Matches                               Description
================== ===================================== ===================================================
{method}           a key in the ``permissions`` dict     If equal to the method it is declared for
                                                         --- e.g. ``{'create': 'create'}`` --- evaluate to:

                                                         ``HybridItemNeed({method}, resource_name)``

                                                         Otherwise re-use needs from other method.
{role}             not a key in the ``permissions`` dict ``RoleNeed({role})``
{method}:{field}     *\*:\**                             Copy ``{method}`` permissions from ``ToOne``
                                                         linked resource at ``{field}``.
user:{field}       *user:\**                             ``UserNeed(item.{field}.id)`` for ``ToOne`` fields.
no                 *no*                                  Do not permit.
yes                *yes*                                 Always permit.
================== ===================================== ===================================================

Example API with permissions
============================

.. code-block:: python

    class UserResource(PrincipalResource):
        class Meta:
            model = User

    class ArticleResource(PrincipalResource):
        author = fields.ToOne('user')
        comments = Relationship('comments')

        class Meta:
            model = Article
            read_only_fields = ['author']
            permissions = {
                'create': 'editor',
                'update': ['user:author', 'admin']
            }

    class CommentResource(PrincipalResource):
        article = fields.ToOne('article')
        author = fields.ToOne('user')

        class Meta:
            model = User
            read_only_fields = ['author']
            permissions = {
                'create': 'yes',
                'update': 'user:author'
                'delete': ['update:article', 'admin']
            }

    @signals.before_create_item.connect
    def before_create_article_comment(sender, item):
        if issubclass(sender, (ArticleResource, CommentResource)):
            item.author_id = current_user.id

    api.decorators = [login_required]

    for resource in (UserResource, ArticleResource, CommmentResource):
        api.add_resource(resource)


In this example, editors can create articles and articles can only be updated or deleted by their authors
or by admins. Comments can be created by anyone who is authenticated, updated only by the commentator, but deleted both by admins
and the author of the article the comment is on.

The :class:`PrincipalResource` class
=====================================


.. autoclass:: principal.PrincipalResource
   :members:

..
    .. autoclass:: principal.needs.HybridNeed
       :members:
    .. autoclass:: principal.permission.HybridPermission
       :members: