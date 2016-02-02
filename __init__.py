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

