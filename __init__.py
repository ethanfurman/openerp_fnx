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

def humanize(browse_record, context=None, _seen=None):
    'return a PropertyDict with all fields converted to text'
    context = context or browse_record._context or {}
    cr = browse_record._cr
    uid = browse_record._uid
    model = browse_record._model
    field_names = model._columns
    seen = _seen or {}
    key = model, browse_record.id
    if key in seen:
        return seen[key]
    record = PropertyDict()
    seen[key] = record
    for field_name in field_names:
        field = model._columns[field_name]
        value = browse_record[field_name]
        if field._type in ('many2one', 'one2many', 'many2many'):
            record[field_name] = value
        elif field._type in ('reference', ):
            if value:
                subrecord = value
                value = subrecord.name_get()[0]
            record[field_name] = value or ''
        elif field._type in ('boolean', ):
            choice = field.choice
            record[field_name] = choice[value]
        elif field._type in ('integer', 'float'):
            record[field_name] = value or 0
        elif field._type in ('float', ):
            record[field_name] = value or 0.0
        elif field._type in ('html', 'text', 'char', 'date', 'binaryname', 'serialized'):
            record[field_name] = value or ''
        elif field._type in ('datetime', ):
            if value:
                value = field.context_timestamp(cr, uid, value, context)
                value = value.strftime('%Y-%m-%d %H:%M')
                record[field_name] = value
            else:
                record[field_name] = ''
        elif field._type in ('binary', ):
            record[field_name] = '%d bytes' % len(value)
        elif field._type in ('selection', ):
            if not value:
                record[field_name] = ''
                continue
            elif isinstance(field.selection, (tuple, list)):
                selection = field.selection
            else:
                # call the 'dynamic selection' function
                selection = field.selection(model, cr, uid, context)
            for internal, user in selection:
                if internal == value:
                    value = user
                    break
            else:
                value = '<invalid internal value: %r>' % value
            record[field_name] = value
        else:
            record[field_name] = '<unk>'
    return record

