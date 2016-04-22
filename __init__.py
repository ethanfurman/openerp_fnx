'''
This portion of fnx should only have classes/functions that are
usable without importing anything from OpenERP (so scripts can safely import fnx)
'''
import sys
if 'openerp' in sys.modules:
    import ir_model

from VSS import address, dbf, enum, finance, path, utils, BBxXlate, time_machine
from VSS.address import *
from VSS.time_machine import PropertyDict
from VSS.utils import *
import logging

_logger = logging.getLogger()

# make dbf and path look like submodules of fnx so other modules can do `from fnx.path import Path'
sys.modules['fnx.address'] = address
sys.modules['fnx.dbf'] = dbf
sys.modules['fnx.enum'] = enum
sys.modules['fnx.finance'] = finance
sys.modules['fnx.path'] = path
sys.modules['fnx.time_machine'] = time_machine
sys.modules['fnx.utils'] = utils
sys.modules['fnx.BBxXlate'] = BBxXlate


class SortedDocEnum(enum.Enum):

    __last_number__ = 0

    def __new__(cls, value, doc=None):
        """Ignores arguments (will be handled in __init__."""
        sequence = cls.__last_number__ + 1
        cls.__last_number__ = sequence
        obj = Super(Enum, cls).__new__(cls)
        obj._value_ = value
        obj._sequence = sequence
        obj.__doc__ = doc
        return obj

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self._sequence >= other._sequence
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self._sequence > other._sequence
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self._sequence <= other._sequence
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self._sequence < other._sequence
        return NotImplemented

    @classmethod
    def export(cls, namespace):
        for name, member in cls.__members__.items():
            if name == member.name:
                namespace[name] = member
    export_to = export


class Humanize(object):
    'a browse_record wrapper that converts fields to text'

    def __init__(self, browse_record, context={}):
        self.context = browse_record._context
        self.context.update(context)
        self.browse_record = browse_record

    def __getattr__(self, name):
        record = self.browse_record
        columns = dict([(k, v[2]) for k, v in record._model._inherit_fields.items()])
        columns.update(record._model._columns)
        value = getattr(record, name)
        if name == 'name_get':
            try:
                return record.name_get()[0][1]
            except Exception, exc:
                return unicode(record[model._rec_name])
                _logger.exception('problem with name_get (%s.%s); using %s' % (model._table, name, result))
        elif name not in columns:
            return value
        cr = record._cr
        uid = record._uid
        model = record._model
        field = columns[name]
        type = field._type
        cls = self.__class__
        if type in ('many2one', ):
            if value:
                result = cls(value, context=self.context)
            else:
                result = value
        elif type in ('one2many', 'many2many'):
            result = [cls(v, context=self.context) for v in value]
        elif type in ('reference', ):
            if value:
                subrecord = value
                value = subrecord.name_get()[0][1]
            result = value or ''
        elif type in ('boolean', ):
            choice = field.choice
            result = choice[value]
        elif type in ('integer', ):
            result = value or 0
        elif type in ('float', ):
            result = value or 0.0
        elif type in ('html', 'text', 'char', 'binaryname', 'serialized'):
            result = value or ''
        elif type in ('datetime', ):
            if value:
                value = field.context_timestamp(cr, uid, value, self.context)
                value = value.strftime('%Y-%m-%d %H:%M')
                result = value
            else:
                result = ''
        elif type in ('date', ):
            if value:
                result = value
            else:
                result = ''
        elif type in ('binary', ):
            result = '%d bytes' % len(value or '')
        elif type in ('selection', ):
            if not value:
                value = ''
            if isinstance(field.selection, (tuple, list)):
                selection = field.selection
            else:
                # call the 'dynamic selection' function
                selection = field.selection(model, cr, uid, self.context)
            for internal, user in selection:
                if internal == value:
                    result = user
                    break
            else:
                if value:
                    result = '<invalid internal value: %r>' % value
                else:
                    result = value
        else:
            value = record[name]
            result = unicode(value) if value else ''
        return result

    def __getitem__(self, name):
        try:
            return getattr(self, name)
        except AttributeError:
            raise KeyError('%s not found' % name)

