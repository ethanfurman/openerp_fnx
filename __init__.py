from VSS import dbf, path
from VSS.utils import *
import ir_model

class Normalize(object):
    """Adds support for normalizing character fields.
    
    `create` and `write` both strip leading and trailing white space, while
    `check_unique` does a case-insensitive compare."""

    def check_unique(self, field, cr, uid, ids, context=None):
        """Case insensitive compare.
        
        Meant to be called as:
        
            lambda *a: self.check_unique(<field>, *a)
        
        """
        existing_ids = self.search(cr, 1, [], context=context)
        values = set([r[field].lower() for r in self.browse(cr, uid, existing_ids, context=context) if r.id not in ids])
        for new_rec in self.browse(cr, uid, ids, context=context):
            if new_rec[field].lower() in values:
                return False
        return True

    def create(self, cr, uid, vals, context=None):
        strip_whitespace(vals)
        return super(Normalize, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        strip_whitespace(vals)
        return super(Normalize, self).write(cr, uid, ids, vals, context=context)


def check_company_settings(obj, cr, uid, *args):
    company = obj.pool.get('res.company')
    company = company.browse(cr, uid, company.search(cr, uid, [(1,'=',1)]))[0]
    values = {}
    if isinstance(args[0][0], tuple):
        all_args = args
    else:
        all_args = (args, )
    for args in all_args:
        for setting, error_name, error_msg in args:
            values[setting] = company[setting]
            if not values[setting]:
                raise ValueError(error_msg % error_name)
    return values

def strip_whitespace(fields):
    """Strips whitespace from all str values in fields"""
    for fld, value in fields.items():
        if isinstance(value, (str, unicode)):
            fields[fld] = value.strip()

