'''
This portion of fnx should only have classes/functions that are
usable without importing anything from OpenERP (so scripts can safely import fnx)
'''

__all__ = ['Humanize', 'ir_model', 'date']

from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp.exceptions import ERPError
import dbf
import ir_model
import logging
from pytz import timezone

utc = timezone('UTC')

_logger = logging.getLogger()

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
            except Exception:
                result = unicode(record[record._rec_name])
                _logger.exception('problem with name_get (%s.%s); using %s' % (record._table, name, result))
                return result
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

def date(year, month=None, day=None):
    if not year:
        return dbf.Date(None)
    elif isinstance(year, basestring):
        return dbf.Date.strptime(year, DEFAULT_SERVER_DATE_FORMAT)
    else:
        return dbf.Date(year, month, day)

def construct_datetime(appt_date, appt_time, context):
    # user_tz = timezone(get_user_timezone(self, cr, uid)[uid])
    # user_tz = timezone('America/Los_Angeles')
    user_tz = timezone(context.get('tz'))
    date = time = None
    if appt_date:
        # will never see an invalid date due to javascript library
        date = dbf.Date(appt_date)
    if appt_time:
        # may see an invalid time
        try:
            time = dbf.Time.fromfloat(appt_time)
        except:
            raise ERPError('Invalid Time', 'Time should be between 0:00 and 23:59 (not %s)' % appt_time)
    else:
        time = dbf.Time(0)
    if date:
        # we have all the pieces, make a datetime
        dt = dbf.DateTime.combine(date, time).datetime()
        dt = user_tz.normalize(user_tz.localize(dt)).astimezone(utc)
        datetime = dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
    else:
        datetime = False
    return datetime
