from __future__ import absolute_import, with_statement

try:
    import __builtin__ as builtins
    from itertools import izip_longest as zip_longest
except ImportError:
    import builtins
    from itertools import zip_longest


import binascii
import dbf
import inspect
from datetime import timedelta
from dbf import Date, Time
from dbf.bridge import baseinteger, basestring

from enhlib.functools import simplegeneric
from enhlib.itertools import all_equal
from enhlib.text import translator


def hrtd(td):
    "human readable time delta"
    seconds = td.total_seconds()
    days, seconds = divmod(seconds, 60*60*24)
    hours, seconds = divmod(seconds, 60*60)
    minutes, seconds = divmod(seconds, 60)
    if seconds:
        minutes += 1
    res = []
    if days:
        res.append('%d days' % days)
    if hours:
        res.append('%d hours' % hours)
    if minutes:
        if minutes != 1:
            res.append('%d minutes' % minutes)
        else:
            res.append('%d minute' % minutes)
    return ', '.join(res)

def Table(fn, *args, **kwds):
    'default to Clipper, Char, Logical, etc'
    data_types = {
            'C' : dbf.Char,
            'L' : dbf.Logical,
            'D' : dbf.Date,
            }
    if 'default_data_types' in kwds:
        data_types.update(kwds['default_data_types'])
    kwds['default_data_types'] = data_types
    if (args or kwds.get('field_specs') is not None):
        new_table = True
    else:
        new_table = False
    if 'dbf_type' not in kwds:
        try:
            possibilities = dbf.guess_table_type(fn)
        except dbf.DbfError:
            possibilities = [('clp',)]
        if len(possibilities) != 1 or 'clp' in [t[0] for t in possibilities]:
            kwds['dbf_type'] = 'clp'
    if new_table:
        kwds['codepage'] = 'utf8'
    return dbf.Table(fn, *args, **kwds)


def bb_text_to_date(text):
    mm, dd, yy = map(int, (text[:2], text[2:4], text[4:]))
    if any([i == 0 for i in (mm, dd, yy)]):
        Date()
    yyyy = yy + 2000
    return Date(yyyy, mm, dd)


def currency(number):
    if not isinstance(number, (baseinteger, basestring)):
        raise ValueError('currency only works with integer and string types (received %s %r )' % (type(number), number))
    if isinstance(number, baseinteger):
        number = str(number)
        number = '0' * (3 - len(number)) + number
        number = number[:-2] + '.' + number[-2:]
    elif isinstance(number, basestring):
        number = int(number.replace('.',''))
    return number


def contains_any(container, *targets):
    for t in targets:
        if t in container:
            return True
    return False

def crc32(binary_data):
    "wrapper around binascii.crc32 that is consistent across python versions"
    return binascii.crc32(binary_data) & 0xffffffff


def unabbreviate(text, abbr):
    """
    returns line lower-cased with standardized abbreviations
    text: text to work with
    abbr: dictionary of abbreviations to use
    """
    text = text.lower().replace(u'\uffa6', ' ')
    words = text.split()
    final = []
    for word in words:
        final.append(abbr.get(word, word))
    return ' '.join(final)



def tuples(func):
    # function returns same type as was passed in (list, tuple, basestring only)
    # ensures `func` receives a tuple
    def wrapper(*args):
        if len(args) > 1:
            data_type = tuple
        elif len(args) == 1 and not isinstance(args[0], basestring):
            args = args[0]
            data_type = type(args)
            args = tuple(args)
        elif len(args) == 1:
            data_type = type(args[0])
        else:
            data_type = tuple
        result = func(*args)
        # result could be: basestring, tuple, list
        # data_type could be: basestring, tuple, list
        # if r is basestring and dt is basestring -> r
        # if r is basestring and dt is tuple/list -> dt((r, ))
        # if r is len(1) tuple/list and dt is basestring -> r[0]
        # if r is len(n) tuple/list and dt is basestring -> raise
        # if r is tuple/list and dt is tuple/list -> dt(r)
        if isinstance(result, basestring) and issubclass(data_type, basestring):
            return result
        elif isinstance(result, basestring):
            return data_type((result, ))
        elif issubclass(data_type, basestring) and len(result) == 1:
            return result[0]
        elif issubclass(data_type, basestring):
            # too much returned
            raise TypeError('%s return %r items as %r (max allowed: 1)' % (func.__name__, len(result), result))
        else:
            return data_type(result)
    wrapper.__name__ = getattr(func, '__name___', None) or getattr(func, 'func_name', 'tuples')
    wrapper.__doc__ = func.__doc__
    return wrapper



phone = translator(delete=' -().etET')
ext = translator(delete=' -().extEXT')

def fix_phone(text):
    text = str(text) # convert numbers to digits
    if not text.strip('0'):
        return ''
    text = text.strip()
    data = phone(text)
    if not data:
        return text
    # fix double leading zeros
    if data[:2] == '00':
        data = '011' + data[2:]
    # fix leading '+' signs
    if data[0] == '+':
        data = '011' + data[1:].replace('+', '')
    data = data.replace('#', 'x').replace('X','x')
    if 'x' in data:
        data, ext = data.split('x', 1)
    else:
        ext = ''
    if ext:
        ext = ' x%s' % ext
    if data.startswith('011'):
        if int(data[3:4]) in (
                20, 27, 30, 31, 32, 33, 34, 36, 39, 40, 41, 43, 44, 45, 46, 47, 49, 49,
                51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64, 65, 66,  7, 81, 82,
                84, 86, 90, 91, 92, 93, 94, 95, 98,
                ):
            pre = [data[:3], data[3:5]]
            data = data[5:]
        else:
            pre = [data[:3], data[3:6]]
            data = data[6:]
        post = [data[-4:]]
        data = data[:-4]
        if len(data) % 4 == 0:
            while data:
                post.append(data[-4:])
                data = data[:-4]
        else:
            while data:
                post.append(data[-3:])
                data = data[:-3]
        post.reverse()
        return '.'.join(pre + post) + ext
    if len(data) not in (7, 10, 11):
        return text
    if len(data) == 11:
        if data[0] != '1':
            return text
        data = data[1:]
    if len(data) == 7:
        return '%s.%s' % (data[:3], data[3:]) + ext
    return '%s.%s.%s' % (data[:3], data[3:6], data[6:]) + ext


def fix_date(text, format='mdy', delta_year=0):
    '''takes mmddyy (with yy in hex (A0 = 2000)) and returns a Date
    
    delta is the number of years to add/subtract from the final date'''
    text = text.strip()
    if len(text) != 6:
        return None
    if format == 'mdy':
        yyyy, mm, dd = text[4:], text[:2], text[2:4]
    elif format == 'ymd':
        yyyy, mm, dd = text[:2], text[2:4], text[4:]
    try:
        yyyy = int(yyyy) + 1900
    except ValueError:
        yyyy = int(yyyy, 16) - 160 + 2000
    mm = int(mm)
    dd = int(dd)
    # auto-back day to inside month if needed
    original_exception = None
    for dd in range(dd, min(dd-1, 27), -1):
        try:
            return Date(yyyy, mm, dd).replace(delta_year=delta_year)
        except Exception as exc:
            if original_exception is None:
                original_exception = exc
            continue
    else:
        raise original_exception

def date(year, month=None, day=None):
    if not year:
        return Date(None)
    elif isinstance(year, basestring):
        return text_to_date(year)
    else:
        return Date(year, month, day)


def grouped(it, size):
    'yield chunks of it in groups of size'
    if size < 1:
        raise ValueError('size must be greater than 0 (not %r)' % size)
    result = []
    count = 0
    for ele in it:
        result.append(ele)
        count += 1
        if count == size:
            yield tuple(result)
            count = 0
            result = []
    if result:
        yield tuple(result)

def grouped_by_column(it, size):
    'yield chunks of it in groups of size columns'
    if size < 1:
        raise ValueError('size must be greater than 0 (not %r)' % size)
    elements = list(it)
    iters = []
    rows, remainder = divmod(len(elements), size)
    if remainder:
        rows += 1
    for column in grouped(elements, rows):
        iters.append(column)
    return zip_longest(*iters, fillvalue='')

def text_to_date(text, format='ymd'):
    '''(yy)yymmdd'''
    if not text.strip():
        return None
    try:
        dd = mm = yyyy = None
        if '-' in text:
            pieces = [p.zfill(2) for p in text.strip().split('-')]
            if len(pieces) != 3 or not all_equal(pieces, lambda p: p and len(p) in (2, 4)):
                raise ValueError
            text = ''.join(pieces)
        elif '/' in text:
            pieces = [p.zfill(2) for p in text.strip().split('/')]
            if len(pieces) != 3 or not all_equal(pieces, lambda p: p and len(p) in (2, 4)):
                raise ValueError
            text = ''.join(pieces)
        if len(text) == 6:
            if format == 'ymd':
                yyyy, mm, dd = int(text[:2])+2000, int(text[2:4]), int(text[4:])
            elif format == 'mdy':
                mm, dd, yyyy = int(text[:2]), int(text[2:4]), int(text[4:])+2000
        elif len(text) == 8:
            if format == 'ymd':
                yyyy, mm, dd = int(text[:4]), int(text[4:6]), int(text[6:])
            elif format == 'mdy':
                mm, dd, yyyy = int(text[:2]), int(text[2:4]), int(text[4:])
    except Exception as exc:
        if exc.args:
            arg0 = exc.args[0] + '\n'
        else:
            arg0 = ''
            exc.args = (arg0 + 'date %r must have two digits for day and month, and two or four digits for year' % text, ) + exc.args[1:]
        raise
    if dd is None:
        raise ValueError("don't know how to convert %r using %r" % (text, format))
    return Date(yyyy, mm, dd)


def text_to_time(text):
    """
    convert text to time
    
    hhmmss... -> hh and mm are required, ss is optional, ... is ignored
    """
    if not text.strip():
        return None
    return Time(int(text[:2]), int(text[2:4]), int(text[4:6] or 0))


@simplegeneric
def float(*args, **kwds):
    return builtins.float(*args, **kwds)


@float.register(timedelta)
def timedelta_as_float(td):
    seconds = td.seconds
    hours = seconds // 3600
    seconds = (seconds - hours * 3600) * (1.0 / 3600)
    return td.days * 24 + hours + seconds


@float.register(Time)
def Time_as_float(t):
    return t.tofloat()


class copy_argspec(object):
    """
    copy_argspec is a signature modifying decorator.  Specifically, it copies
    the signature from `source_func` to the wrapper, and the wrapper will call
    the original function (which should be using *args, **kwds).
    """
    def __init__(self, src_func):
        self.argspec = inspect.getargspec(src_func)
        self.src_doc = src_func.__doc__
        self.src_defaults = src_func.func_defaults

    def __call__(self, tgt_func):
        tgt_argspec = inspect.getargspec(tgt_func)
        need_self = False
        if tgt_argspec[0][0] == 'self':
            need_self = True
            
        name = tgt_func.__name__
        argspec = self.argspec
        if argspec[0][0] == 'self':
            need_self = False
        if need_self:
            newargspec = (['self'] + argspec[0],) + argspec[1:]
        else:
            newargspec = argspec
        signature = inspect.formatargspec(formatvalue=lambda val: "", *newargspec)[1:-1]
        new_func = (
                'def _wrapper_(%(signature)s):\n' 
                '    return %(tgt_func)s(%(signature)s)' % 
                {'signature':signature, 'tgt_func':'tgt_func'}
                   )
        evaldict = {'tgt_func' : tgt_func}
        exec(new_func, evaldict)
        wrapped = evaldict['_wrapper_']
        wrapped.__name__ = name
        wrapped.__doc__ = self.src_doc
        wrapped.func_defaults = self.src_defaults
        return wrapped


class LazyAttr(object):
    "doesn't create instance object until actually accessed from an instance"
    def __init__(self, func=None, doc=None, name=None):
        self.fget = func
        self.__doc__ = doc or func.__doc__
        self.name = name
    def __call__(self, func):
        self.fget = func
    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.name is not None:
            result = self.fget()
        else:
            result = self.fget(instance)
        setattr(instance, self.name or self.fget.__name__, result)
        return result

class LazyClassAttr(object):
    "doesn't create class object until actually accessed"
    def __init__(self, func=None, doc=None, name=None):
        self.fget = func
        self.__doc__ = doc or func.__doc__
        self.name = name
    def __call__(self, func):
        self.fget = func
    def __get__(self, instance, owner):
        if instance is None or self.name is not None:
            result = self.fget()
        else:
            result = self.fget(instance)
        setattr(owner, self.name or self.fget.__name__, result)
        return result
    def __set_name__(self, ownerclass, name):
        self.name = name


class Open(object):
    builtin_open = open
    _cache = {}
    @classmethod
    def __call__(cls, name, *args):
        file = cls.builtin_open(name, *args)
        cls._cache[name] = file
        return file
    @classmethod
    def active(cls, name):
        cls.open_files()
        try:
            return cls._cache[name]
        except KeyError:
            raise ValueError('%s has been closed' % name)
    @classmethod
    def open_files(cls):
        closed = []
        for name, file in cls._cache.items():
            if file.closed:
                closed.append(name)
        for name in closed:
            cls._cache.pop(name)
        return cls._cache.items()

