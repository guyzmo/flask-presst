from collections import namedtuple
from operator import and_
from flask.ext.restful import abort
from jsonschema import validate, ValidationError
from sqlalchemy import func
from . import fields

__author__ = 'lyschoening'


Comparator = namedtuple('Comparator', ['name', 'expression', 'schema', 'supported_types'])

DEFAULT_COMPARATORS = (
    Comparator('$eq',
                lambda column, value: column == value,
                lambda field: field.schema,
                (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$neq',
                lambda column, value: column != value,
                lambda field: field.schema,
                (fields.Boolean, fields.String, fields.Integer, fields.Number)),
    Comparator('$in',
               lambda column, value: column.in_(value) if len(value) else False,
               lambda field: {
                   "type": "array",
                   # "minItems": 1, # NOTE: Permitting 0 items for now.
                   "uniqueItems": True,
                   "items": field.schema  # NOTE: None is valid.
               },
               (fields.String, fields.Integer, fields.Number)),
    Comparator('$lt',
               lambda column, value: column < value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$gt',
               lambda column, value: column > value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$leq',
               lambda column, value: column <= value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$geq',
               lambda column, value: column >= value,
               lambda field: {"type": "number"},
               (fields.Integer, fields.Number)),
    Comparator('$ts',
               lambda column, value: column.op('@@')(func.plainto_tsquery(value)),
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               (fields.String,)),
    Comparator('$startswith',
               lambda column, value: column.startswith(value.replace('%', '\\%')),
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               (fields.String,)),
    Comparator('$endswith',
               lambda column, value: column.endswith(value.replace('%', '\\%')),
               lambda field: {
                   "type": "string",
                   "minLength": 1
               },
               (fields.String,))

)


class Filter(object):
    """
    :param allowed_filters:

        - ``"*"`` filtering allowed on all supported field types
        - ``["f1", "f2"]`` filtering allowed on fields ``'f1'`` and ``'f2'``, provided they are supported.
        - ``{"f1": ["$eq", "$lt"], "f2": "*"}`` restrict available comparators.

    """

    comparators = {c.name: c for c in DEFAULT_COMPARATORS}
    comparators_by_type = {
        f: [c for c in DEFAULT_COMPARATORS if f in c.supported_types]
        for f in (fields.Boolean, fields.String, fields.Integer, fields.Number)
    }

    #
    def __init__(self, model, fields=None, allowed_filters=None):
        self.allowed_filters = None
        self.model = model
        self.fields = {}

        if allowed_filters in ('*', None):
            allowed_filters = '*'
        elif isinstance(allowed_filters, (list, tuple)):
            allowed_filters = {field: '*' for field in allowed_filters}
        elif isinstance(allowed_filters, dict):
            pass

        for name, field in fields.items():
            try:
                available_comparators = self.comparators_by_type[field.__class__]
            except KeyError:
                continue

            if allowed_filters == '*':
                self.fields[name] = field, available_comparators
            elif name in allowed_filters:
                if allowed_filters[name] == '*':
                    comparators = available_comparators
                else:
                    comparators = [c for c in allowed_filters[name] if c in available_comparators]

                self.fields[name] = field, comparators

    def get_schema(self):
        pass

    def get_field_where_schema(self, field):
        comparators = self.comparators_by_type[field.__class__]

        explicit_options = {
            "type": "object",
            "properties": {c.name: c.schema(field) for c in comparators},
            "minProperties": 1,
            "maxProperties": 1,
        }

        if self.comparators['$eq'] in comparators:
            return {
                "oneOf": [
                    explicit_options,
                    self.comparators['$eq'].schema(field)
                ]
            }

        return explicit_options

    def _where_expression(self, where):
        expressions = []

        for name, where_clause in where.items():
            field, comparators = self.fields[name]
            column = getattr(self.model, field.attribute)

            try:
                validate(where_clause, self.get_field_where_schema(field))
            except ValidationError as ve:
                abort(400, message="Bad filter: {}".format(where_clause))

            comparator = None
            value = None

            if isinstance(where_clause, dict):
                for c in comparators:
                    if c.name in where_clause:
                        comparator = c
                        value = where_clause[c.name]
                        break

                if not comparator:
                    abort(400, message='Bad filter expression: {}'.format(where_clause))
            elif isinstance(where_clause, list):
                comparator = self.comparators['$in']
                value = where_clause
            else:
                comparator = self.comparators['$eq']
                value = where_clause

            expressions.append(comparator.expression(column, value))

        if len(expressions) == 1:
            return expressions[0]

        # TODO ranking by default with text-search.

        return and_(*expressions)

    def _sort_criteria(self, sort):
        for name, order in sort.items():
            field, _ = self.fields[name]
            column = getattr(self.model, field.attribute)

            # TODO validate sort with schema.

            if field.__class__ not in (fields.String, fields.Boolean, fields.Number, fields.Integer):
                abort(400, message='Sorting not supported for "{}"'.format(name))

            if order == -1:
                yield column.desc()
            else:
                yield column.asc()

    def apply(self, query, where, sort):
        if where:
            query = query.filter(self._where_expression(where))
        if sort:
            query = query.order_by(*self._sort_criteria(sort))
        return query

