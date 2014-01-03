from flask.ext.presst import fields
from flask.ext.presst.resources import PresstResource


class Tree(PresstResource):
    type = fields.String()

    class Meta:
        resource_name = 'tree'
        required_fields = ['type']
