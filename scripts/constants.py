from aenum import Enum, IntEnum
from datetime import timedelta
from dbf import Date
from enhlib.misc import basestring

import dbf

__all__ = [
        'Enum', 'IntEnum', 'AutoEnum', 'IndexEnum', 'FederalHoliday', 'Month', 'Weekday',
        ]

one_day = timedelta(1)


class AutoEnum(Enum):
    """
    Automatically numbers enum members starting from 1.
    Includes support for a custom docstring per member.
    """

    __last_number__ = 0

    def __new__(cls, *args):
        """Ignores arguments (will be handled in __init__."""
        value = cls.__last_number__ + 1
        cls.__last_number__ = value
        obj = object.__new__(cls)
        obj._value_ = value
        return obj

    def __init__(self, *args):
        """Can handle 0 or 1 argument; more requires a custom __init__.
        0  = auto-number w/o docstring
        1  = auto-number w/ docstring
        2+ = needs custom __init__
        """
        if len(args) == 1 and isinstance(args[0], basestring):
            self.__doc__ = args[0]
        elif args:
            raise TypeError('%s not dealt with -- need custom __init__' % (args,))

    def __index__(self):
        return self.value

    def __int__(self):
        return self.value

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    @classmethod
    def export(cls, namespace):
        for name, member in cls.__members__.items():
            if name == member.name:
                namespace[name] = member
    export_to = export


class IndexEnum(Enum):

    def __index__(self):
        return self.value

    def __int__(self):
        return self.value

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.value > other.value
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    @classmethod
    def export(cls, namespace):
        for name, member in cls.__members__.items():
            if name == member.name:
                namespace[name] = member
    export_to = export

class Weekday(AutoEnum):
    __order__ = 'MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY SATURDAY SUNDAY'
    MONDAY = ()
    TUESDAY = ()
    WEDNESDAY = ()
    THURSDAY = ()
    FRIDAY = ()
    SATURDAY = ()
    SUNDAY = ()
    @classmethod
    def from_abbr(cls, abbr):
        abbr = abbr.upper()
        if abbr in ('', 'T'):
            raise ValueError('unknown abbreviation: %r' % (abbr, ))
        for day in cls:
            if day.name.startswith(abbr):
                return day
        raise ValueError('unknown abbreviation: %r' % (abbr, ))
    @classmethod
    def from_date(cls, date):
        return cls(date.isoweekday())
    def next(self, day):
        """Return number of days needed to get from self to day."""
        if self == day:
            return 7
        delta = day - self
        if delta < 0:
            delta += 7
        return delta
    def last(self, day):
        """Return number of days needed to get from self to day."""
        if self == day:
            return -7
        delta = day - self
        if delta > 0:
            delta -= 7
        return delta
MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = Weekday


class Month(AutoEnum):
    __order__ = 'JANUARY FEBRUARY MARCH APRIL MAY JUNE JULY AUGUST SEPTEMBER OCTOBER NOVEMBER DECEMBER'
    JANUARY = ()
    FEBRUARY = ()
    MARCH = ()
    APRIL = ()
    MAY = ()
    JUNE = ()
    JULY = ()
    AUGUST = ()
    SEPTEMBER = ()
    OCTOBER = ()
    NOVEMBER = ()
    DECEMBER = ()

    @classmethod
    def from_date(cls, date):
        return cls(date.month)
JANUARY, FEBRUARY, MARCH, APRIL, MAY, JUNE, JULY, AUGUST, SEPTEMBER, OCTOBER, NOVEMBER, DECEMBER = Month


class FederalHoliday(AutoEnum):
    __order__ = 'NewYear MartinLutherKingJr President Memorial Independence Labor Columbus Veterans Thanksgiving Christmas'
    NewYear = "First day of the year.", 'absolute', JANUARY, 1
    MartinLutherKingJr = "Birth of Civil Rights leader.", 'relative', JANUARY, MONDAY, 3
    President = "Birth of George Washington", 'relative', FEBRUARY, MONDAY, 3
    Memorial = "Memory of fallen soldiers", 'relative', MAY, MONDAY, 5
    Independence = "Declaration of Independence", 'absolute', JULY, 4
    Labor = "American Labor Movement", 'relative', SEPTEMBER, MONDAY, 1
    Columbus = "Americas discovered", 'relative', OCTOBER, MONDAY, 2
    Veterans = "Recognition of Armed Forces service", 'relative', NOVEMBER, 11, 1
    Thanksgiving = "Day of Thanks", 'relative', NOVEMBER, THURSDAY, 4
    Christmas = "Birth of Jesus Christ", 'absolute', DECEMBER, 25

    def __init__(self, doc, type, month, day, occurance=None):
        self.__doc__ = doc
        self.type = type
        self.month = month
        self.day = day
        self.occurance = occurance

    def date(self, year):
        "returns the observed date of the holiday for `year`"
        if self.type == 'absolute' or isinstance(self.day, int):
            holiday =  Date(year, self.month, self.day)
            if Weekday.from_date(holiday) is SUNDAY:
                holiday = holiday.replace(delta_day=1)
            return holiday
        days_in_month = dbf.days_in_month(year)
        target_end = self.occurance * 7
        if target_end > days_in_month[self.month]:
            target_end = days_in_month[self.month]
        target_start = target_end - 6
        target_week = list(xrange(start=Date(year, self.month, target_start), step=one_day, count=7))
        for holiday in target_week:
            if Weekday.from_date(holiday) is self.day:
                return holiday

    @classmethod
    def next_business_day(cls, date, days=1):
        """
        Return the next `days` business day from date.
        """
        holidays = cls.year(date.year)
        years = set([date.year])
        day = Weekday.from_date(date)
        while "not at target business day":
            if days == 0 and day not in (SATURDAY, SUNDAY) and date not in holidays:
                return date
            date = date.replace(delta_day=1)
            if date.year not in years:
                holidays.extend(cls.year(date.year))
                years.add(date.year)
            day = Weekday.from_date(date)
            if day in (SATURDAY, SUNDAY) or date in holidays:
                continue
            if days > 0:
                days -= 1

    @classmethod
    def count_business_days(cls, date1, date2):
        """
        Return the number of business days between start and order.
        """
        date1 = Date(date1)
        date2 = Date(date2)
        if date2 < date1:
            date1, date2 = date2, date1
        holidays = cls.year(date1.year)
        years = set([date1.year])
        day = Weekday.from_date(date1)
        day_count = 0
        while "not at target":
            if date1 == date2:
                return day_count
            date1 = date1.replace(delta_day=1)
            if date1.year not in years:
                holidays.extend(cls.year(date1.year))
                years.add(date1.year)
            day = Weekday.from_date(date1)
            if day not in (SATURDAY, SUNDAY) and date1 not in holidays:
                day_count += 1

    @classmethod
    def year(cls, year):
        """
        Return a list of the actual FederalHoliday dates for `year`.
        """
        holidays = []
        for fh in cls:
            holidays.append(fh.date(year))
        return holidays


__all__ += list(Month.__members__) + list(Weekday.__members__)

