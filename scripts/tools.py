from __future__ import print_function
from collections import defaultdict
from sys import exc_info

import errno
import os
import re
import warnings

from abc import ABCMeta, abstractmethod
from aenum import Enum, Flag, NamedConstant, NamedTuple
from antipathy import Path
from dbf import Date, DateTime, Time, Table, READ_WRITE
from dbf import NoneType, NullType, Char, Logical
from fnx_script_support import grouped_by_column
from openerplib import DEFAULT_SERVER_DATE_FORMAT, get_records, get_xid_records, XidRec
from openerplib import Fault, PropertyNames, IDEquality, ValueEquality, Many2One, SetOnce
from scription import print, echo, error, ViewProgress, script_verbosity, abort, empty
from traceback import format_exception
from VSS.address import cszk, Rise, Sift, AddrCase, BsnsCase, NameCase, PostalCode
from VSS.BBxXlate.fisData import fisData
from VSS.utils import all_equal, LazyClassAttr

virtualenv = os.environ['VIRTUAL_ENV']

class K(NamedConstant):
    OE7 = 0
    Odoo13 = 1

OE7 = K.OE7
Odoo13 = K.Odoo13
odoo_erp = Odoo13 if 'odoo' in virtualenv else OE7

 # keep pyflakes happy
script_verbosity
abort
FIS_ID = None
FIS_MODULE = None

DRYRUN = False

@PropertyNames
class XmlLink(IDEquality):
    """
    create singleton object, allow fields to be set only once
    """

    xml_id = SetOnce()
    id = SetOnce()
    _cache = {}
    _other_fields = set()
    # "host" is set by SynchronizeType

    def __new__(cls, xml_id, id=None, **kwds):
        if isinstance(id, str):
            raise Exception('oops -> %r %r' % (xml_id, id))
        if xml_id not in cls._cache.setdefault(cls, {}):
            link = super(XmlLink, cls).__new__(cls)
            link.xml_id = xml_id
            if id is not None:
                link.id = id
            cls._cache[cls][xml_id] = link
        link = cls._cache[cls][xml_id]
        for k, v in kwds.items():
            setattr(link, k, v)
        return link

    def __repr__(self):
        return "%s(xml_id=%r, id=%r)" % (self.__class__.__name__, self.xml_id, self.id)

    def __getattr__(self, name):
        if not hasattr(self, 'host'):
            raise TypeError("%s missing 'host' field" % (self, ))
        if name not in self.host.OE_FIELDS_LONG:
            "%r not in %s.OE_FIELDS_LONG" % (name, self.host.__class__.__name__)
        return XmlLinkField(self, name)


@PropertyNames
class XmlLinkField(ValueEquality):
    """
    soft reference to a record's field
    """

    value = SetOnce()
    _cache = {}

    def __new__(cls, link, field_name):
        if (link, field_name) not in cls._cache:
            obj = object.__new__(cls)
            obj.link = link
            obj.name = field_name
            cls._cache[link, field_name] = obj
        obj = cls._cache[link, field_name]
        obj.link.__class__._other_fields.add(field_name)
        return obj

    @property
    def names(self):
        return self.link.__class__._other_fields

    def __repr__(self):
        return ("<%s: link=%r, field_name=%r, value=%r>"
                % (
                    self.__class__.__name__,
                    self.link,
                    self.name, self.value,
                    ))

class NewRecord(object):
    """
    hold the details for a new record for an m2o link
    """
    def __init__(self, **values):
        self.values = values
    def __repr__(self):
        return 'NewRecord(%s)' % ', '.join([
                '%s=%r' % (k, v)
                for k, v in sorted(self.values.items())
                ])


class PsuedoFisTable(object):
    """
    an FIS table look-alike for more complex data match-ups
    """

    __slots__ = 'filename', 'data'

    def __init__(self, filename):
        self.filename = filename
        self.data = {}
    
    def __len__(self):
        return len(self.data)

    def __getattr__(self, name):
        return getattr(self.data, name)
    
    def __getitem__(self, name):
        return self.data[name]
    
    def __setitem__(self, name, value):
        self.data[name] = value


Synchronize = None

class SynchronizeType(ABCMeta):

    def __new__(metacls, cls_name, bases, clsdict):
        cls = super(SynchronizeType, metacls).__new__(metacls, cls_name, bases, clsdict)
        if not cls_name.startswith('Synchronize'):
            try:
                absmethods = list(cls.__abstractmethods__)
                if absmethods:
                    absmethods_str = ', '.join('%r' % method for method in absmethods)
                    plural = 's' if len(absmethods) > 1 else ''
                    raise TypeError(
                        "cannot instantiate abstract class %r"
                        " with abstract method%s %s" 
                        % (cls_name, plural, absmethods_str)
                        )
            except AttributeError:
                pass
            # verify presence of class settings
            missing = []
            for setting in (
                    'TN', 'FN', 'RE', 'OE', 'F', 'IMD',
                    'FIS_KEY', 'OE_KEY', 'FIS_IGNORE_RECORD', 'FIS_SCHEMA',
                ):
                if getattr(cls, setting, empty) is empty:
                    missing.append(setting)
            
            for setting in ('OE_FIELDS', 'OE_FIELDS_LONG'):
                if getattr(cls, setting, None):
                    break
            else:
                missing.append('OE_FIELDS, OE_FIELDS_LONG, and/or OE_FIELDS_QUICK')
            if missing:
                raise TypeError('%s: missing attribute(s):\n\t%s'
                        % (cls_name, '\n\t'.join(missing)),
                        )
            # fill in missing settings
            if getattr(cls, 'OE_FIELDS', None):
                if getattr(cls, 'OE_FIELDS_LONG', None):
                    raise TypeError('cannot specify both OE_FIELDS and OE_FIELDS_LONG')
                if getattr(cls, 'OE_FIELDS_QUICK', None):
                    raise TypeError('cannot specify both OE_FIELDS and OE_FIELDS_QUICK')
                setattr(cls, 'OE_FIELDS_LONG', cls.OE_FIELDS)
            if not getattr(cls, 'OE_FIELDS_QUICK', None):
                setattr(cls, 'OE_FIELDS_QUICK', cls.OE_FIELDS_LONG)
            # create XmlLinks if needed
            for name, obj in clsdict.items():
                if obj is XmlLink:
                    obj = type(name, (XmlLink, ), {'host':cls, })
                    setattr(cls, name, obj)
                    setattr(cls, 'XmlLink', obj)
                    # there should only be one XmlLink -- this makes sure the
                    # class breaks sooner rather than later
                    break
        return cls

SynchronizeABC = SynchronizeType(
        'SynchronizeABC',
        (object, ),
        {
            '__repr__':lambda s: "%s(%r, %r)" % (s.__class__.__name__, s.erp, s.config),
            '__str__': lambda s: "%s" % (s.__class__.__name__, ),
            },
        )

class Synchronize(SynchronizeABC):

    FIS_ADDRESS_FIELDS = ()
    FIS_IGNORE_RECORD = lambda self, rec: False
    OE_KEY_MODULE = None
    FIELDS_CHECK_IGNORE = ()

    def FIS_IGNORE_RECORD(self, rec):
        if self.extra.get('key_filter') is None:
            return False
        elif self.extra['key_filter'] == rec[self.FIS_KEY]:
            return False
        else:
            return True

    get_fis_table = staticmethod(fisData)
    get_xid_records = staticmethod(get_xid_records)
    get_records = staticmethod(get_records)

    errors = defaultdict(lambda: defaultdict(list))

    def __init__(self, connect, config, extra=None):
        """
        class level variables that need to be set

            TN  -> FIS table number
            FN  -> FIS table file name
            RE  -> re.match for selecting FIS records
            OE  -> OE model name
            F   -> formated table number, used as prefix for imd name [ 'F262' or 'F163_F65' ]
            IMD -> (Odoo) table name, used as suffix for imd name
            FIS_KEY             -> key field in FIS tables
            OE_KEY              -> key field in OE tables
            OE_FIELDS_LONG      -> OE fields to fetch for long comparisons
            FIS_SCHEMA          -> FIS fields to use for quick comparisons

        If needed:

            FIS_IGNORE_RECORD   -> function to determine if FIS record should be skipped
            OE_FIELDS_QUICK     -> OE fields to fetch for quick comparisons
            OE_KEY_MODULE       -> module field value or field and value, if any
            FIELDS_CHECK_IGNORE -> fields to ignore during integrity check
        """
        self.dryrun = DRYRUN
        self.erp = connect
        self.config = config
        self.context = {'fis-updates': True, 'active_test': False}
        self.model = self.erp.get_model(self.OE)
        self.ir_model_data = self.erp.get_model('ir.model.data')
        self.extra = extra or {}
        #
        # get the "old" data from:
        # - quick -> old fis file
        # - full -> current OpenERP data
        #
        self.oe_records = {}
        self.fis_records = {}
        self.changed_records = {}
        self.new_records = {}
        self.remove_records = {}
        self.need_normalized = {}
        # the counts
        self.changed_count = 0
        self.added_count = 0
        self.deleted_count = 0

    @classmethod
    def calc_xid(cls, key):
        imd_name = '%s_%s_%s' % (cls.F, key, cls.IMD)
        return imd_name.replace('-','_').replace(':','_')

    def categorize(self):
        """
        split records into changed, added, and deleted groups
        """
        print('categorizing...')
        print('fis record keys: %r\noe record keys:  %r' % (self.fis_records.keys(), self.oe_records.keys()), verbose=3)
        all_keys = set(list(self.fis_records.keys()) + list(self.oe_records.keys()))
        print('all keys: %r' % (all_keys, ), verbose=3)
        change_records = 0
        for key in sorted(all_keys):
            old = self.oe_records.get(key)
            new = self.fis_records.get(key)
            if old is new is None:
                # not sure how this happened, but it looks like we can ignore it
                continue
            elif old is None:
                # no matching OE record, so add the FIS record
                self.new_records[key] = new
            elif new is None:
                if 'active' in old and not old.active:
                    # record is already inactive, ignore
                    continue
                # no matching FIS record, so delete/deactivate the OE record
                self.remove_records[key] = old
            else:
                # we have an old and a new record -- update the FIS record with
                # relevant fields from the OE record
                self.normalize_records(new, old)
                if new == old:
                    # no changes, move on
                    continue
                changes = {}
                for field in self.OE_FIELDS:
                    if old[field] != new[field]:
                        if not old[field] and not new[field]:
                            print('old', old, verbose=2)
                            print('new', new, verbose=2)
                            print('[%s] %r:  %r != %r' % (key, field, old[field], new[field]), border='flag', verbose=2)
                        new_value = new[field]
                        if isinstance(new_value, list):
                            new_value = tuple(new_value)
                        changes[field] = new_value
                try:
                    self.changed_records.setdefault(
                            tuple(sorted(changes.items())),
                            list(),
                            ).append(old)
                except TypeError:
                    print(changes)
                    raise
                change_records += 1
        print('  %d records to be added' % len(self.new_records))
        for rec in self.new_records.values()[:10]:
            print('    %r' % rec, verbose=2)
        print('  %d changes to be made across %d records' % (len(self.changed_records), change_records))
        for changes, records in self.changed_records.items()[:10]:
            print('    %r\n      %r' % (changes, records[0]), verbose=2)
        print('  %d records to be deleted' % len(self.remove_records))
        for rec in self.remove_records.values()[:10]:
            print('    %r' % rec, verbose=2)

    def check_integrity(self):
        """
        perform integrity checks on FIS and OpenERP data

        - no duplicate keys in FIS
        - no duplicate keys in OE
        - each record in FIS matches a record in OE
        - vice versa
        """
        errors = {}
        # load fis records
        fis_dupes = {}
        fis_records = self.fis_records
        self.open_fis_tables()
        for entry in ViewProgress(
                self.fis_table.values(),
                message='converting $total FIS records',
            ):
            for rec in self.convert_fis_rec(entry, use_ignore=True):
                if rec is None:
                    continue
                key = rec[self.OE_KEY]
                if key in fis_records:
                    fis_dupes.setdefault(key, []).append(rec)
                fis_records[key] = rec
        # load openerp records
        oe_dupes = {}
        domain = []
        if self.OE_KEY_MODULE:
            value = self.OE_KEY_MODULE
            module = 'module'
            if isinstance(value, tuple):
                module, value = value
            domain.append((module,'=',self.OE_KEY_MODULE))
        oe_records = self.oe_records
        print('retrieving OE records...')
        for rec in ViewProgress(
                get_records(
                    self.erp, self.OE,
                    domain=domain,
                    fields=self.OE_FIELDS_LONG,
                    type=XidRec,
                    ),
                message='converting $total OE records',
                view_type='percent',
            ):
            key = rec[self.OE_KEY]
            if key in oe_records:
                oe_dupes.setdefault(key, []).append(rec)
            oe_records[key] = rec
        # verify fis records
        for dupe_key in fis_dupes:
            # hopefully, they are all equal
            unique = [fis_records[dupe_key]]
            dupes = fis_dupes[dupe_key]
            for rec in dupes:
                if rec not in unique:
                    unique.append(rec)
            if len(unique) == 1:
                errors.setdefault(dupe_key, {})['fis'] = '%d identical records' % (1 + len(dupes))
                errors.setdefault(dupe_key, {})['identical'] = True
            else:
                errors.setdefault(dupe_key, {})['fis'] = (
                        '%d different records amongst %d identical records'
                            % (len(unique), 1+(len(dupes)))
                            )
                errors.setdefault(dupe_key, {})['identical'] = False
        # verify openerp records
        for dupe_key in oe_dupes:
            # hopefully, they are all equal
            unique = [oe_records[dupe_key]]
            dupes = oe_dupes[dupe_key]
            for rec in dupes:
                if rec not in unique:
                    unique.append(rec)
            if len(unique) == 1:
                errors.setdefault(dupe_key, {})['oe'] = '%d identical records' % (1 + len(dupes))
            else:
                errors.setdefault(dupe_key, {})['oe'] = (
                        '%d different records amongst %d identical records'
                            % (len(unique), 1+(len(dupes)))
                            )
        # normalize FIS records
        self.normalize_fis('full')
        # compare FIS records to OpenERP records
        all_keys = sorted(set(list(fis_records.keys()) + list(oe_records.keys())))
        for key in ViewProgress(
                all_keys,
                message='comparing $total records',
                view_type='percent',
            ):
            fis_rec = fis_records.get(key)
            oe_rec = oe_records.get(key)
            if fis_rec is None:
                if 'active' not in oe_rec or oe_rec.active:
                    errors.setdefault(key, {})['fis'] = 'missing'
            elif oe_rec is None:
                errors.setdefault(key, {})['oe'] = 'missing'
            else:
                self.normalize_records(fis_rec, oe_rec)
                for field in self.FIELDS_CHECK_IGNORE:
                    del fis_rec[field]
                    del oe_rec[field]
                if fis_rec != oe_rec:
                    fis_diff = []
                    oe_diff = []
                    check_fields = [
                            f
                            for f in self.OE_FIELDS_QUICK
                            if f not in self.FIELDS_CHECK_IGNORE
                            ]
                    for field in check_fields:
                        try:
                            fis_val = fis_rec[field]
                        except KeyError:
                            error(fis_rec, oe_rec, border='box')
                            raise KeyError('%s: no FIS key named %r' % (self.__class__.__name__, field))
                        try:
                            oe_val = oe_rec[field]
                        except KeyError:
                            error(fis_rec, None, oe_rec, border='box')
                            raise KeyError('%s: no OE key named %r' % (self.__class__.__name__, field))
                        if fis_val != oe_val:
                            fis_diff.append('%s->  %s' % (field, fis_val))
                            oe_diff.append('%s' % (oe_val, ))
                    if fis_diff:
                        string = '\n'.join(fis_diff)
                        prev = errors.setdefault(key, {}).setdefault('fis', None)
                        if prev is not None:
                            string = prev + '\n' + string
                        errors[key]['fis'] = string
                    if oe_diff:
                        string = '\n'.join(oe_diff)
                        prev = errors.setdefault(key, {}).setdefault('oe', None)
                        if prev is not None:
                            string = prev + '\n' + string
                        errors[key]['oe'] = string
        if not errors:
            echo('FIS and OpenERP records for %s/%d match (%d total)' % (self.FN.upper(), self.TN, len(all_keys)))
        else:
            table = [('xml id', 'FIS', 'OpenERP'), None]
            i = 0
            for key, values in sorted(errors.items()):
                i += 1
                if not i % 50:
                    table.extend([None, ('fis_id', 'FIS', 'OpenERP'), None])
                table.append((
                    repr(key).replace(' ','\\s').replace('\t','\\t')[2:-1] or '<empty key>',
                    errors[key].get('fis', ''),
                    errors[key].get('oe', ''))
                    )
            echo('%s - %s' % (self.__class__.__name__, self.OE))
            echo(table, border='table')

    def close_dbf_log(self):
        """
        close file and delete if empty
        """
        self.record_log.close()
        if not self.record_log:
            table = Path(self.record_log.filename)
            memo = Path(self.record_log.memoname)
            if table.exists():
                table.unlink()
            if memo.exists():
                memo.unlink()

    @abstractmethod
    def convert_fis_rec(self, record):
        """
        return a tuple of (XidRec, ...) suitable for OE
        """
        pass

    def create_dbf_log(self):
        """
        create dbf

        field names come from the class
        field specs come from the model
        """
        # create dbf log file
        path = Path(os.environ.get('VIRTUAL_ENV') or '')
        if path:
            path /= 'var/log/sync-updates'
            if not path.exists():
                path.mkdir()
        specs = ['action_ C(10)', 'failure_ M null']
        names = []
        for name in ('id',self.OE_KEY,'name','street','street2','city','state_id','zip','country_id'):
            if name in names:
                # self.OE_KEY is also 'name'
                continue
            if name in self.model._as_dbf:
                names.append(name)
        for name in sorted(self.model._as_dbf):
            if name not in names:
                names.append(name)
        specs.extend([
                '%s null' % self.model._as_dbf[name].spec
                for name in names
                if name in self.OE_FIELDS_LONG
                ])
        self.dbf_fields = dict(
                (name, dns.name)
                for name, dns in self.model._as_dbf.items()
                if name in self.OE_FIELDS_LONG
                )
        self.record_log = Table(
                filename=(
                    '%s/%03d_%s-%s.dbf'
                    % (path, self.TN, self.FN, DateTime.now().strftime('%Y_%m_%d-%H_%M_%S'))
                    ),
                field_specs=specs,
                codepage='utf8',
                default_data_types=dict(
                        C=(Char, NoneType, NullType),
                        L=(Logical, NoneType, NullType),
                        D=(Date, NoneType, NullType),
                        T=(DateTime, NoneType, NullType),
                        M=(Char, NoneType, NullType),
                        ),
                dbf_type='vfp',
                ).open(READ_WRITE)

    def global_updates(self):
        """
        any code that needs to run after all records have been processed
        """
        return

    def fis_long_load(self):
        """
        load entire FIS table
        """
        self.open_fis_tables()
        print(self.fis_table.filename, verbose=2)
        print('loading current FIS data...', end=' ')
        oe_module = self.OE_KEY_MODULE
        for entry in self.fis_table.values():
            for rec in self.convert_fis_rec(entry, use_ignore=True):
                key = rec[self.OE_KEY]
                if oe_module:
                    key = oe_module, key
                self.fis_records[key] = rec
        print('%d records retrieved' % len(self.fis_records))
        print('  ', '\n   '.join(str(r) for r in self.fis_records.values()), verbose=3)
        return None

    def fis_quick_load(self):
        """
        load all FIS records that have changes
        """
        self.open_fis_tables()
        print(self.fis_table.filename, verbose=2)
        print(self.old_fis_table.filename, verbose=2)
        print('loading current and most recent FIS data...', end=' ')
        changes, added, deleted = self.get_fis_changes()
        print('%d and %d records loaded' % (len(self.fis_table), len(self.old_fis_table)))
        imd_names = set()
        oe_module = self.OE_KEY_MODULE
        for old, new, diffs in changes:
            old_entries = self.convert_fis_rec(old)
            new_entries = self.convert_fis_rec(new)
            for old_rec, new_rec in zip(old_entries, new_entries):
                if old_rec != new_rec:
                    key = new_rec[self.OE_KEY]
                    if oe_module:
                        key = oe_module, key
                    self.fis_records[key] = new_rec
                    imd_names.add(new_rec._imd.name)
        for entry in added:
            for rec in self.convert_fis_rec(entry):
                key = rec[self.OE_KEY]
                if oe_module:
                    key = oe_module, key
                self.fis_records[key] = rec
                imd_names.add(rec._imd.name)
        for entry in deleted:
            for rec in self.convert_fis_rec(entry):
                key = rec[self.OE_KEY]
                if oe_module:
                    key = oe_module, key
                self.fis_records[key] = rec
                imd_names.add(rec._imd.name)
        return tuple(imd_names)

    def get_fis_changes(self, key=None):
        """
        compare the current and old versions of an FIS table

        key, if not specified, defaults to all the key fields for that table
        return changed, added, and deleted records
        """
        # get changed records as list of
        # (old_record, new_record, [(enum_schema_member, old_value, new_value), (...), ...]) tuples
        try:
            if issubclass(self.FIS_SCHEMA, Enum):
                enum = self.FIS_SCHEMA
        except TypeError:
                enum = type(self.FIS_SCHEMA[0])
        if key is None:
            key_fields_name = list(enum)[0].fis_name
            key_fields = [m for m in enum if m.fis_name == key_fields_name]
        else:
            key_fields = key
        address_fields = self.FIS_ADDRESS_FIELDS
        enum_schema = [m for m in self.FIS_SCHEMA if m not in address_fields]
        changes = []
        added = []
        deleted = []
        old_records_map = {}
        new_records_map = {}
        for rec in self.old_fis_table.values():
            key = []
            for f in key_fields:
                key.append(rec[f])
            key = tuple(key)
            old_records_map[key] = rec
        for rec in self.fis_table.values():
            key = []
            for f in key_fields:
                key.append(rec[f])
            key = tuple(key)
            new_records_map[key] = rec
        all_recs = set(new_records_map.keys() + old_records_map.keys())
        ignore = self.FIS_IGNORE_RECORD
        for key in all_recs:
            changed_values = []
            new_rec = new_records_map.get(key)
            old_rec = old_records_map.get(key)
            if new_rec and ignore(new_rec):
                new_rec = None
            if old_rec and ignore(old_rec):
                old_rec = None
            if new_rec == old_rec:
                continue
            if new_rec is None:
                deleted.append(old_rec)
                continue
            if old_rec is None:
                added.append(new_rec)
                continue
            for field in address_fields:
                if new_rec[field] != old_rec[field]:
                    # add all the address fields and dump out of the loop
                    for field in address_fields:
                        changed_values.append((field, old_rec[field], new_rec[field]))
                    break
            for field in enum_schema:
                if new_rec[field] != old_rec[field]:
                    changed_values.append((field, old_rec[field], new_rec[field]))
            if changed_values:
                changes.append((old_rec, new_rec, changed_values))
        return changes, added, deleted

    def ids_from_fis_ids(self, convert, fis_ids):
        xid_names = [convert(fid) for fid in fis_ids]
        print('    xid_names ->', xid_names[:10], verbose=2)
        records = self.ir_model_data.search_read([
                ('module','=','fis'),
                ('name','in',xid_names),
                ],
                fields=['res_id'],
                )
        print('    %d records found' % len(records), verbose=2)
        return [r.res_id for r in records]

    def ids_from_fis_records(self, *dicts):
        xid_names = list(set([
                r._imd.name
                for d in dicts
                for r in d.values()
                ]))
        records = self.ir_model_data.search([
                ('module','=','fis'),
                ('name','in',xid_names),
                ])
        return [r.res_id for r in records]


    def imd_domain_from_fis_records(self, *dicts):
        xid_names = list(set([
                r._imd.name
                for d in dicts
                for r in d.values()
                ]))
        return [
                ('module','=','fis'),
                ('name','in',xid_names),
                ]

    def log(self, action, *records):
        result = []
        for rec in records:
            # values = {'action_': action, 'id': Null}
            values = {'action_': action}
            for k, v in rec.items():
                print('logging %s: %r' % (k, v), verbose=3)
                if k.endswith('_'):
                    dbf_field = k
                else:
                    dbf_field = self.dbf_fields[k]
                if isinstance(v, Many2One):
                    v = v.name if v.id else None
                elif isinstance(v, XmlLink):
                    v = v.xml_id if v.id else None
                elif isinstance(v, XmlLinkField):
                    error('extracting %s from %s' % (v.value, v))
                    v = v.value if v else None
                elif isinstance(v, basestring):
                    if not v: v = None
                elif isinstance(v, (bool, int, long, float)):
                    pass
                elif isinstance(v, (Date, DateTime, Time, NoneType)):
                    v = v if v else None
                elif isinstance(v, (list, tuple)) and v:
                    lines = []
                    for links in grouped_by_column(v, 3):
                        lines.append('%-10s %-10s %-10s' % links)
                    v = '\n'.join(lines)
                else:
                    v = str(v) if v else None
                values[dbf_field] = v
            if action in ('change','delete'):
                values['id'] = rec.id
            try:
                self.record_log.append(values)
                result.append(self.record_log.last_record)
            except ValueError:
                self.record_log.append(None)
                error('unable to log %r' % (values, ))
        return result

    def log_exc(self, exc, record):
        failure = str(exc).replace('\\n','\n')
        values = {'failure_': failure}
        values.update(record)
        self.log('failed', *(values, ))
        self.errors['%s-%s-%s' % (self.F, self.FN, self.OE)][failure].append(record)

    def normalize_fis(self, method):
        """
        fills in the target id of each link

        method can be 'quick' or 'full', which subclasses may make use of
        """
        print('normalizing...')
        if not(self.fis_records):
            return
        fields = []
        sub_fields = {}
        check_fields = self.fis_records.values()[0].keys()
        #
        # gather the fields that may be links
        #
        for rec in self.fis_records.values():
            for field_name in check_fields:
                value = rec[field_name]
                if value is not None:
                    check_fields.remove(field_name)
                    if isinstance(value, XmlLink):
                        fields.append((field_name, value.host))
                    if isinstance(value, XmlLinkField):
                        sub_fields.setdefault(field_name, set()).update(value.names)
            if not check_fields:
                break
        if not fields:
            return
        else:
            print('  ', ', '.join([f[0] for f in fields]), verbose=2)
        #
        # gather the fis (xml) ids needed
        #
        for field_name, host in ViewProgress(
                fields,
                message='updating $total field(s)',
            ):
            # host = CSMS
            # host.OE = 'res.partner'
            # host.OE_KEY = 'xml_id'
            # host.OE_KEY_MODULE = 'F33'
            needed = {}
            for rec in self.fis_records.values():
                link = rec[field_name]
                if link is None or link.id:
                    continue
                # link.xml_id = 'HE477'
                # link.id = None
                needed[link.xml_id] = link
            print('  needed:', sorted(needed.keys()[:10]), verbose=2)
            model = host.OE
            key = host.OE_KEY
            print('  model: %r\n  key: %r' % (model, key), verbose=2)
            #
            # get the needed records from OpenERP
            #
            oe_records = dict(
                    (r[key], r)
                    for r in get_records(
                        self.erp, model,
                        ids=self.ids_from_fis_ids(
                            host.calc_xid,
                            [p.xml_id for p in needed.values()],
                            ),
                        fields=['id', key] + list(sub_fields.get(field_name, ())),
                        context=self.context,
                        ))
            print('  found:', sorted(oe_records.items()[:10]), verbose=2)
            for xml_id, link in needed.items():
                # link is the pointer to the foriegn record
                # value is the foreign record
                value = oe_records.get(xml_id, None)
                if isinstance(link, XmlLinkField):
                    link.value = value and getattr(value, link.name)
                else:
                    link.id = value and value.id
                if host is self.__class__:
                    # this part only works for self-referencial fields
                    if link.id is None:
                        self.need_normalized[xml_id] = link

    def normalize_records(self, fis_rec, oe_rec):
        """
        copy appropriate data from oe records to matching fis records
        """
        fis_rec.id = oe_rec.id
        fis_rec._imd = oe_rec._imd

    def oe_load_data(self, xid_names=None):
        """
        load oe records using ir.model.data
        restrict by names
        """
        print('loading OE data...', end=' ')
        if xid_names:
            domain = [
                    ('module','=','fis'),
                    ('name','in',xid_names),
                    ]
        elif self.extra.get('key_filter') is not None:
            domain=[
                ('module','=','fis'),
                ('model','=',self.OE),
                ('name','=like','%s_%s_%s' % (self.F, self.extra['key_filter'], self.IMD),)
                ]

        else:
            domain=[
                ('module','=','fis'),
                ('model','=',self.OE),
                ('name','=like','%s_%%_%s' % (self.F, self.IMD),)
                ]
        module = self.OE_KEY_MODULE
        key = self.OE_KEY
        for rec in self.get_xid_records(
                self.erp,
                domain=domain,
                fields=self.OE_FIELDS,
                context=self.context,
            ):
            if self.extra.get('key_filter') is not None:
                if self.extra['key_filter'] != rec[self.OE_KEY]:
                    continue
            key = rec[self.OE_KEY]
            if module:
                key = module, key
            self.oe_records[key] = rec 
        print('%d records retrieved' % len(self.oe_records))

    def open_fis_tables(self):
        self.fis_table = self.get_fis_table(self.TN, rematch=self.RE)
        self.old_fis_table = self.get_fis_table(
                self.TN,
                rematch=self.RE,
                data_path=self.config.network.fis_data_local_old_path,
                )

    def record_additions(self):
        """
        create new records in OE
        """
        for key, rec in ViewProgress(
                sorted(self.new_records.items()),
                message='adding $total records...',
                view_type='percent',
            ):
            [log_record] = self.log('add', rec)
            try:
                # make sure an x2many fields are in the correct format
                for key, value in rec.items():
                    if key in self.model._x2many_fields:
                        if not value:
                            rec[key] = [(5, )]
                        else:
                            ids = []
                            for x in value:
                                if isinstance(x, IDEquality):
                                    x = x.id
                                elif isinstance(x, ValueEquality):
                                    x = x.value
                                ids.append(x)
                            rec[key] = [(6, 0, ids)]
                if self.dryrun:
                    return
                else:
                    new_id = self.model.create(rec)
                    if log_record is not None:
                        with log_record:
                            log_record.id = new_id
            except Exception as exc:
                vals = {self.OE_KEY: rec[self.OE_KEY]}
                if self.OE_KEY_MODULE:
                    value = self.OE_KEY_MODULE
                    module = 'module'
                    if isinstance(value, tuple):
                        module, value = value
                    vals[module] = value
                self.log_exc(exc, vals)
                continue
            self.added_count += 1
            rec.id = new_id
            self.oe_records[key] = rec
            if rec[self.OE_KEY] in self.need_normalized:
                link = self.need_normalized.pop(rec[self.OE_KEY])
                link.id = new_id

    def record_changes(self):
        """
        commit all changes to OE
        """
        for changes, records in ViewProgress(
                self.changed_records.items(),
                message='recording $total change groups...',
                view_type='percent',
            ):
            changes = dict(changes)
            ids = [r.id for r in records]
            self.log('delta', changes)
            self.log('change', *records)
            try:
                field_names = changes.keys()
                for fn in field_names:
                    if fn in self.model._x2one_fields:
                        # enusre x2o fields are passed correctly
                        value = changes[fn]
                        if isinstance(value, NewRecord):
                            changes[fn] = (0, 0, value.values)
                    elif fn in self.model._x2many_fields:
                        # ensure x2m fields are passed correctly
                        value = changes[fn]
                        if not value:
                            changes[fn] = [(5, )]
                        else:
                            value_ids = []
                            for x in value:
                                if isinstance(x, IDEquality):
                                    x = x.id
                                elif isinstance(x, ValueEquality):
                                    x = x.value
                                value_ids.append(x)
                            changes[fn] = [(6, 0, value_ids)]
                if self.dryrun:
                    return
                else:
                    self.model.write(ids, changes)
                    self.changed_count += len(ids)
            except Exception as exc:
                self.log_exc(exc, changes)

    def record_deletions(self):
        """
        remove all deletions from OE
        """
        # try the fast method first
        try:
            action = ('delete','deactivate')['active' in self.OE_FIELDS]
            actioning = action[:-1] + 'ing'
            print('%s %d records' % (actioning, len(self.remove_records)))
            ids = [r.id for r in self.remove_records.values()]
            if self.dryrun:
                return
            else:
                if action == 'delete':
                    self.model.unlink(ids)
                else:
                    self.model.write(ids, {'active': False})
            oe_records = self.oe_records.copy()
            self.oe_records.clear()
            self.oe_records.update(dict(
                (k, v)
                for k, v in oe_records.items()
                if k not in self.remove_records
                ))
            self.deleted_count += len(self.remove_records)
            self.log(action, *self.remove_records.values())
        except Fault:
            # that didn't work, do it the slow way
            for key, rec in ViewProgress(
                    self.remove_records.items(),
                    message='recording $total %s' % (('deletes','deactivations')[action=='deactivate']),
                    view_type='percent',
                ):
                self.log(action, rec)
                try:
                    if action == 'deactivate':
                        self.model.write(rec.id, {'active': False})
                    else:
                        self.model.unlink(rec.id)
                    self.deleted_count += 1
                    self.oe_records.pop(key)
                except Fault as exc:
                    vals = {self.OE_KEY: rec[self.OE_KEY]}
                    if self.OE_KEY_MODULE:
                        value = self.OE_KEY_MODULE
                        module = 'module'
                        if isinstance(value, tuple):
                            module, value = value
                        vals[module] = value
                    self.log_exc(exc, vals)

    def reify(self, fields=[]):
        """
        generate all XmlLinks, and attach OE fields to them
        """
        for rec in self.get_xid_records(
                self.erp,
                domain=[
                    ('module','=','fis'),
                    ('model','=',self.OE),
                    ('name','=like','%s_%%_%s' % (self.F, self.IMD),)
                    ],
                fields=list(set(fields + ['id', self.OE_KEY])),
                context=self.context,
            ):
            link = self.XmlLink(rec[self.OE_KEY], rec.id)
            for f in fields:
                setattr(link, f, rec[f])

    def run(self, method):
        #
        # get the "old" data from:
        # - quick -> old fis file
        # - full -> current OpenERP data
        #
        print('=' * 80)
        self.method = method
        self.create_dbf_log()
        try:
            print('processing %s...' % self.__class__.__name__)
            if method == 'quick':
                self.load_fis_data = self.fis_quick_load
                self.OE_FIELDS = self.OE_FIELDS_QUICK
            elif method == 'full':
                self.load_fis_data = self.fis_long_load
                self.OE_FIELDS = self.OE_FIELDS_LONG
            elif method == 'check':
                self.OE_FIELDS = self.OE_FIELDS_LONG
                self.check_integrity()
                return
            elif method == 'imd-update':
                self.OE_FIELDS = self.OE_FIELDS_QUICK
                self.update_imd()
                return
            else:
                raise ValueError('unknown METHOD: %r' % (method, ))
            names = self.load_fis_data()    # load fis data
            # an empty tuple is possible with method=QUICK and no changes/additions/deletions
            # in which case we don't want to do anything else
            if names != ():
                self.oe_load_data(names)        # load oe data
                self.normalize_fis(method)      # adjust fis data as needed
                self.categorize()               # split into changed, added, deleted groups
            self.record_deletions()         # deletions first, in case imd changed
            self.record_additions()
            self.record_changes()
            self.global_updates()
        finally:
            if method in ('quick', 'full'):
                print()
                print('%d mappings added\n%d mappings changed\n%d mappings %s'
                        % (
                            self.added_count,
                            self.changed_count,
                            self.deleted_count,
                            ('deleted','deactivated')['active' in self.OE_FIELDS],
                            ),
                        border='box',
                        )
            self.close_dbf_log()

    def update_imd(self):
        updated = 0
        skipped = 0
        self.oe_load_data()
        # self.oe_records now has all records that have ir.model.data names
        xid_names = {}
        ids = set()
        for rec in self.oe_records.values():
            xid_names[rec._imd.name] = rec
            ids.add(rec.id)
        ids = list(ids)
        needed_fields = ['id', self.OE_KEY]
        domain = [('id','not in',ids)]
        module_field = FIS_MODULE
        module_value = self.OE_KEY_MODULE
        if isinstance(module_value, tuple):
            module_field, module_value = self.OE_KEY_MODULE
        if module_value:
            domain.append((module_field,'=',module_value))
            needed_fields.append(module_field)
        bare_oe_records = get_records(
                self.erp,
                self.OE,
                domain=domain,
                fields=needed_fields,
                )
        for rec in ViewProgress(
                bare_oe_records,
                message='$total possible records found',
                view_type='percent',
            ):
            xid_name = self.calc_xid(rec[self.OE_KEY])
            if xid_name in xid_names:
                skipped += 1
                error(
                    '[%(id)s] %(key)s: %(xid_name)s already taken by [%(existing_id)s] %(display_name)s'
                    % {
                        'id': rec.id,
                        'key': rec[self.OE_KEY],
                        'xid_name': xid_name,
                        'existing_id': xid_names[xid_name]._imd.res_id,
                        'display_name': xid_names[xid_name]._imd.display_name,
                        })
                continue
            self.ir_model_data.create({
                    'module': 'fis',
                    'name': xid_name,
                    'model': self.OE,
                    'res_id': rec.id,
                    })
            xid_names.update(dict(
                    (r.name, r)
                    for r in self.ir_model_data.search_read(
                        domain=[
                            ('module','=','fis'),
                            ('name','=',xid_name),
                            ],
                        fields=['name','model','res_id','display_name'],
                        )))
            updated += 1
        return updated, skipped

class SynchronizeAddress(Synchronize):

    def __init__(self, connect, config, state_recs=None, country_recs=None, *args, **kwds):
        self.state_recs = state_recs
        self.country_recs = country_recs
        super(SynchronizeAddress, self).__init__(connect, config, *args, **kwds)

    def normalize_records(self, fis_rec=None, oe_rec=None):
        super(SynchronizeAddress, self).normalize_records(fis_rec, oe_rec)
        if 'fis_updated_by_user' in self.OE_FIELDS:
            fis_rec.fis_updated_by_user = oe_rec.fis_updated_by_user
            user_updates = fis_rec.fis_updated_by_user or ''
            try:
                if 'A' in user_updates:
                    # drop all the address fields
                    oe_rec.use_parent_address = None
                    oe_rec.street = oe_rec.street2 = None
                    oe_rec.city = oe_rec.state_id = oe_rec.zip = oe_rec.country_id = None
                    fis_rec.use_parent_address = None
                    fis_rec.street = fis_rec.street2 = None
                    fis_rec.city = fis_rec.state_id = fis_rec.zip = fis_rec.country_id = None
                if 'N' in user_updates:
                    oe_rec.name = None
                    fis_rec.name = None
                if 'S' in user_updates:
                    oe_rec.specials_notification = None
                    fis_rec.specials_notification = None
            except AttributeError:
                error(oe_rec, fis_rec, sep='\n---\n', border='box')
                raise

    def process_name_address(self, schema, fis_rec, home=False):
        address = {}
        address_lines = (
                fis_rec[schema.name],
                fis_rec[schema.addr1],
                fis_rec[schema.addr2],
                fis_rec[schema.addr3],
                )
        name, do_not_use, addr1, addr2, city, state, postal, country = process_name_address(address_lines)
        if home:
            sf = 'home_street'
            s2f = 'home_street2'
            cf = 'home_city'
            sidf = 'home_state_id'
            zf = 'home_zip'
            kidf = 'home_country_id'
        else:
            sf = 'street'
            s2f = 'street2'
            cf = 'city'
            sidf = 'state_id'
            zf = 'zip'
            kidf = 'country_id'
        address[sf] = addr1 or None
        address[s2f] = addr2 or None
        address[cf] = city or None
        address[zf] = postal or None
        address[sidf] = None
        address[kidf] = None
        if state:
            address[sidf] = self.state_recs[state][0]
            address[kidf] = country = self.state_recs[state][1]
        elif country:
            country_id = self.country_recs.get(country, None)
            if country_id:
                address[kidf] = country_id
            elif city:
                city += ', ' + country
                address[cf] = city
            else:
                city = country
                address[cf] = city
        return name, address, do_not_use


# helpers

class DocFlag(Flag):
    _init_ = 'value __doc__'
    def __repr__(self):
        return '%s.%s' % (self.__class__.__name__, self._name_)
    def __str__(self):
        return self._name_


class AddressSegment(DocFlag):
    #
    _order_ = 'UNKNOWN PO PO_TYPE NUMBER PREORD NAME STREET POSTORD SECONDARY_TYPE SECONDARY_NUMBER AND'
    #
    UNKNOWN = "unable to determine address element type"
    PO = "post office delivery"
    PO_TYPE = "box or drawer"
    NUMBER = "main unit designator"
    PREORD = "N S E W etc"
    NAME = "street name"
    STREET = "st ave blvd etc"
    POSTORD = "N S E W etc"
    SECONDARY_TYPE = "apt bldg floor etc"
    SECONDARY_NUMBER = "secondary unit designator"
    AND = "& indicates a corner address"
    #
    def has_any(self, flags):
        return (False, True)[any(f in self for f in flags)]

AS = AddressSegment
UNKNOWN, PO, PO_TYPE, NUMBER, PREORD, NAME, STREET, POSTORD, SECONDARY_TYPE, SECONDARY_NUMBER, AND = AddressSegment
SECONDARY = SECONDARY_TYPE | SECONDARY_NUMBER

after_name = NUMBER | NAME | STREET | POSTORD | SECONDARY

# possible address layouts
# PO PO_TYPE NUMBER
# NUMBER [PREORD] NAME [STREET] [POSTORD] [SECONDARY_TYPE] [SECONDARY_NUMBER]
# [SECONDARY_TYPE] SECONDARY_NUMBER

def tokenize_address_line(line):
    u_line = line.upper()
    u_words = u_line.replace(',',' ').split()
    if 'ST RT' in u_line and 'ST' in u_words and 'RT' in u_words and u_words.index('ST') + 1 == u_words.index('RT'):
        index = u_words.index('ST')
        u_words[index:index+2] = ['ST RT']
    o_u_words = u_words[:]
    o_u_words
    if len(u_words) < 2:
        return False, u_words, [UNKNOWN]
    po = False
    final = []
    tokens = []
    # check for po box
    po_line = u_line.replace('.',' ').split()
    if po_line[0] in ('POB', 'POBOX'):
        po = True
        po_line.pop(0)
        final.extend(['PO', 'BOX'])
        tokens.extend([PO, PO_TYPE])
    elif po_line[0] == 'PO' and po_line[1] in ('BOX', 'DRAWER'):
        po = True
        final.extend(po_line[:2])
        po_line = po_line[2:]
        tokens.extend([PO, PO_TYPE])
    elif len(po_line) >= 3 and po_line[0] == 'P' and po_line[1] == 'O' and po_line[2] in ('BOX', 'DRAWER'):
        po = True
        final.append('PO')
        tokens.extend([PO, PO_TYPE])
        final.append(po_line[2])
        po_line = po_line[3:]
    if po:
        # only a designator should remain
        if len(po_line):
            final.append(po_line.pop(0))
            tokens.append(NUMBER)
        while po_line:
            final.append(po_line.pop(0))
            tokens.append(UNKNOWN)
        valid = UNKNOWN not in tokens
        return valid, final, tokens
    elif u_words == ['GENERAL', 'DELIVERY']:
        final.extend(u_words)
        u_words = []
        tokens.extend([PO, PO_TYPE])
        return True, final, tokens
    # look for common addresses
    expected = NUMBER | NAME | SECONDARY
    valid = None
    token = AS(0)
    while u_words:
        last_token = token
        test_word = u_words.pop(0)
        if test_word in ('&', 'AND'):
            token = AND
            new_expected = PREORD | NAME
            tokens.append(token)
            final.append(test_word)
            continue
        elif test_word == '/':
            token = UNKNOWN
            new_expected = UNKNOWN
            tokens.append(token)
        elif test_word == '#' and u_words:
            # merge with next word
            u_words[0] = '#' + u_words[0]
            continue
        elif (
                any(w == test_word for w in ('ONE','TWO','THREE','FOUR','FIVE','SIX','SEVEN','EIGHT','NINE','TEN'))
                or (
                    any(n in '0123456789' for n in test_word) and
                    not test_word.endswith(('ST','ND','RD','TH'))
            )):
            if last_token is NUMBER and u_words: # and u_words[0] in ('ST','ND','RD','TH'):
                # possible error with a split street name, e.g. '24', 'TH'
                # classify this as a NAME instead, but do not combine as ST could be street
                # and RD could be road (instead of 1st or 3rd)
                token = NAME
                new_expected = after_name
            # either a number or a secondary
            elif last_token & SECONDARY_TYPE:
                tokens[-1] = SECONDARY_TYPE
                token = SECONDARY_NUMBER
                new_expected = SECONDARY_TYPE
            elif last_token is NAME | STREET:
                # previous was a street, this is a name
                tokens[-1] = STREET
                token = NAME
                new_expected = after_name
            elif last_token & PREORD:
                token = NAME
                new_expected = after_name
            elif test_word.isdigit() or test_word.isalpha():
                token = NUMBER
                new_expected = PREORD | NAME
                if tokens[-1:] == [PREORD | NAME] and tokens[-2:-1] == [NUMBER]:
                    tokens[-1] = NAME
            else:
                token = NUMBER | SECONDARY
                new_expected = PREORD | NAME | SECONDARY_TYPE
            tokens.append(token)
            # followed by a fraction?
            if u_words and u_words[0].count('/') == 1:
                num, den = u_words[0].split('/')
                if num.isdigit() and den.isdigit():
                    test_word = '%s %s' % (test_word, u_words.pop(0))
        elif (
                any(n in '0123456789' for n in test_word) and
                test_word.endswith(('ST','ND','RD','TH'))
            ):
            if last_token & NUMBER:
                tokens[-1] = NUMBER
                token = NAME
                new_expected = after_name
            elif last_token & (STREET | POSTORD | SECONDARY):
                token = SECONDARY_NUMBER
                new_expected = SECONDARY_TYPE
            else:
                token = NAME
                new_expected = after_name
            tokens.append(token)
        elif test_word.replace('.','') in ('NW','NE','SW','SE') or test_word in ('N.','S.','E.','W.'):
            # an ordinal, either pre- or post-
            if last_token & NUMBER:
                tokens[-1] = NUMBER
                token = PREORD
                new_expected = NAME
            elif last_token & (NAME | STREET):
                token = POSTORD
                new_expected = SECONDARY
            elif not tokens or last_token is AND:
                # maybe it's a corner address: NW 16th & NW Havanah
                token = PREORD
                new_expected = NAME
            else:
                # not sure what happened, save for diagnostics
                token = UNKNOWN
                new_expected = UNKNOWN
            tokens.append(token)
            test_word = test_word.replace('.','')
        elif test_word in ('N','S','E','W','NORTH','SOUTH','EAST','WEST'):
            # either a pre- or post-ordinal or a name or a secondary number
            if last_token & NUMBER:
                token = PREORD | NAME
                new_expected = NUMBER | NAME | STREET | SECONDARY_TYPE
            elif last_token & PREORD:
                tokens[-1] = PREORD
                token = NAME
                new_expected = after_name
            elif last_token & (STREET | NAME):
                token = NAME | POSTORD
                new_expected = after_name
            elif last_token & SECONDARY_TYPE:
                token = SECONDARY_NUMBER
                new_expected = SECONDARY
            elif not last_token or last_token is AND:
                # maybe it's a corner address: N 16th & W Havanah
                token = NUMBER | PREORD | NAME
                new_expected = after_name
            else:
                # not sure what happened, save for diagnostics
                token = UNKNOWN
                new_expected = UNKNOWN
            tokens.append(token)
        elif test_word in usps_street_suffix_common:
            if not last_token:
                token = NAME
                new_expected = after_name
            else:
                # not sure what happened, save for diagnostics
                token = NAME | STREET
                new_expected = after_name
            tokens.append(token)
        elif test_word in usps_secondary:
            # a name or a secondary type (apt, bldg, etc.)
            if not last_token:
                # beginning of line
                token = SECONDARY_TYPE
                new_expected = SECONDARY_NUMBER
            elif last_token & (NUMBER | PREORD):
                token = NAME | SECONDARY_TYPE
                new_expected = after_name
            elif last_token & (STREET | POSTORD | SECONDARY_NUMBER):
                # 121 main blvd APT
                # 121 main ne SUITE
                # bldg 5, FLOOR 4
                token = SECONDARY_TYPE
                new_expected = SECONDARY_NUMBER
            elif last_token & NAME:
                if last_token & SECONDARY_TYPE:
                    tokens[-1] = NAME
                token = NAME | SECONDARY_TYPE
                new_expected = after_name
            else:
                # not sure what happened, save for diagnostics
                token = UNKNOWN
                new_expected = UNKNOWN
            tokens.append(token)
        else:
            # doesn't match anything else, could be a name or some kind of secondary
            # or even part of the first number
            if test_word[0] == '#' and any(ch.isalnum() for ch in test_word):
                if tokens == [NUMBER]:
                    final[-1] = '%s %s' % (final[-1], test_word)
                    continue
                else:
                    token = SECONDARY
                    new_expected = SECONDARY
            elif last_token is SECONDARY_TYPE:
                # unless the last thing seen was a secondary
                token = SECONDARY_NUMBER
                new_expected = SECONDARY
            elif last_token & SECONDARY_TYPE:
                token = NAME | SECONDARY_NUMBER
                new_expected = after_name
            elif last_token is SECONDARY_NUMBER:
                # continue secondaries
                token = SECONDARY
                new_expected = SECONDARY
            else:
                token = NAME
                new_expected = after_name
                for i, earlier in reversed(list(enumerate(tokens))):
                    if earlier is NAME:
                        break
                    elif earlier & NAME:
                        continue
                else:
                    i = -1
                if i != -1:
                    while i < len(tokens):
                        tokens[i] = NAME
                        i += 1
            tokens.append(token)
        if valid is None:
            if token & expected:
                valid = True
        elif token is UNKNOWN or not token & expected:
            valid = False
        final.append(test_word)
        expected = new_expected
    else:
        # no break above, so always runs
        # put loop cleanup code here
        # adjust tokens from back to front
        #
        # NUMBER, PREORD, NAME, STREET, POSTORD, SECONDARY_TYPE, SECONDARY_NUMBER
        orig_tokens = tokens[:]
        orig_tokens
        preord = name = street = postord = secondary = False
        for i in reversed(range(len(tokens))):
            token = tokens[i]
            before = i and tokens[i-1] or None
            if not secondary and SECONDARY_TYPE & token:
                if token is not SECONDARY:
                    tokens[i] = SECONDARY_TYPE
                secondary = True
            elif not postord and POSTORD & token:
                tokens[i] = POSTORD
                postord = secondary = True
            elif not street and STREET & token:
                tokens[i] = STREET
                street = postord = secondary = True
            elif not name and NAME & token:
                tokens[i] = NAME
                name = postord = secondary = True
            elif not preord and PREORD & token and before and not NAME & before:
                tokens[i] = PREORD
                preord = True
            elif NAME & token:
                tokens[i] = NAME
            elif NUMBER & token:
                tokens[i] = NUMBER
        if 'JR' in final:
            # it should be 'Jr' if last item on line, or succeeds another NAME element
            ind = final.index('JR')
            if ind == len(final) - 1 or tokens[ind-1] is NAME:
                final[ind] = 'Jr'
    # final sanity check
    if valid:
        if len(tokens) == 1:
            valid = False
        elif all_equal(tokens):
            valid = False
        elif len(tokens) == 2 and tokens not in (
                [PO, PO_TYPE],
                [NUMBER, STREET],
                [SECONDARY_TYPE, SECONDARY_NUMBER],
                [SECONDARY_NUMBER, SECONDARY_TYPE],
            ):
            valid = False
        elif len(tokens) > 2 and set(tokens[:-1]) == set([NAME]):
            valid = False
    return valid, final, tokens

def process_name_address(address):
    name, do_not_use, address_lines = split_name_address(address)
    # move STORE lines from address to name
    for line in address_lines[:]:
        if line.startswith('STORE '):
            name.append(line.replace('-',' '))
            address_lines.remove(line)
    name = BsnsCase(name)
    if len(address_lines) < 2:
        # ensure we have at least two address lines
        address_lines = (address_lines + ['', ''])[:2]
    address_lines = Sift(address_lines)
    if ' / ' in address_lines[-2]:
        # could be two street address lines in one
        # could be a street address and part of the cszk
        # could be garbage
        #
        # just split 'em and be done
        pieces = address_lines[-2].split(' / ')
        address_lines[-2:-1] = [p.strip('/ ') for p in pieces if p.strip()]
    if ' / ' in address_lines[-1]:
        # might be a street and then a cszk
        pieces = address_lines[-1].split(' / ')
        address_lines[-1:] = [p.strip('/ ') for p in pieces if p.strip()]
    # test if last address line is a valid address
    valid, final, tokens = tokenize_address_line(address_lines[-1])
    if tokens == [NUMBER, NAME, STREET]:
        # no city, state, zip
        city = state = postal = country = ''
    else:
        street2, city, state, postal, country = cszk(address_lines[-2], address_lines[-1])
        if city and not (street2 or state or postal or country):
            # totally bogus address
            street2, city = city, street2
        address_lines = address_lines[:-2]
        if street2.strip():
            address_lines.append(street2)
        city = NameCase(city)
        state = NameCase(state)
        postal = str(postal)
    if country not in ('CANADA', 'UNITED STATES'):
        if len(address_lines) == 3:
            # combine second and third lines
            address_lines[1:] = [('%s, %s' % (address_lines[1], address_lines[2])).strip(', ')]
        elif len(address_lines) >= 4:
            # combine first and second, and third +
            address_lines[0] = ', '.join(address_lines[:2])
            address_lines[1] = ', '.join(address_lines[1:])
        address_lines = BsnsCase(address_lines)
    else:
        lines = []
        valid_lines = []
        secondary_lines = []
        invalid_lines = []
        for line in address_lines:
            valid, line, tokens = tokenize_address_line(line)
            new_line = []
            if not valid:
                line = BsnsCase(' '.join(line))
                lines.append(line)
                invalid_lines.append(line)
            else:
                for word, token in zip(line, tokens):
                    if token & (PREORD | POSTORD) and len(word) > 2:
                        word = word[0]
                    elif token & STREET:
                        word = usps_street_suffix(word).title()
                    elif token & SECONDARY:
                        word = usps_secondary.get(word, word).title()
                    new_line.append(word)
                line = AddrCase(' '.join(new_line))
                if tokens and tokens[0] & SECONDARY:
                    secondary_lines.append(line)
                lines.append(line)
                valid_lines.append(line)
        lines = [l for l in lines if l.strip()]
        if len(lines) > 2:
            # need to combine
            if invalid_lines and len(invalid_lines) > 1:
                # first do invalid
                lines = [', '.join(invalid_lines)] + valid_lines
            if len(lines) > 2:
                # then do secondary
                if secondary_lines:
                    new_lines = []
                    secondary = []
                    for line in lines:
                        if line in secondary_lines:
                            secondary.append(line)
                        else:
                            new_lines.append(line)
                        if new_lines:
                            while secondary:
                                new_lines[-1] = '%s, %s' % (new_lines[-1], secondary.pop(0))
                    lines = new_lines
            if len(lines) > 2:
                # mash 'em together
                lines[1:] = [', '.join(lines[1:])]
        address_lines = lines
    address_lines = [a for a in address_lines if a.strip()]
    if len(address_lines) < 2:
        # need to have two address lines
        address_lines = (address_lines + ['', ''])[:2]
    try:
        addr1, addr2 = address_lines
    except ValueError:
        raise ValueError("need two address_lines, but received %r" % (address_lines, ))
    return name, do_not_use, addr1, addr2, city, state, postal, country

def split_name_address(lines):
    """
    if possible, combine first two lines into a name, next two lines into an address;
    return name and remaining lines
    """
    # first line is always a name, but may have a second name as well
    # second line could be a name, or the last part of a second name,
    #   or a second and third name
    #   (or an address)
    #   (or a ** line to be ignored)
    if not lines[0].strip():
        return [], [], [l.strip() for l in lines[1:]]
    lines = [smart_upper(l) for l in Rise(lines) if l.strip()]
    ignore = []
    lines_to_check = []
    for line in lines:
        if line.strip().startswith((
                '*',
                'ACCOUNT CLOSED',
                'BUSINESS CLOSED',
                'BUSINESS SOLD',
                'BANKRUPT',
                'CLOSED AS OF',
                'STORE CLOSED',
            )):
            ignore.append(line)
        else:
            lines_to_check.append(line)
    lines = lines_to_check
    if len(lines) > 1 and not lines[1].startswith(('LOCKBOX', 'DEPT', 'ATTN', 'PO', 'ADDITION')):
        # look for three lines in two
        test = ' '.join(lines[:2])
        if test.count(' / ') == 2:
            lines[:2] = test.split(' / ')
        # handle Mother's Market & Kitchen
        elif lines[0].startswith('MOTHER') and lines[1].startswith('& KITCHEN'):
            line, extra = lines[0], ''
            if '-' in line:
                line, extra = line.split('-', 1)
                extra = ' - %s' % extra
            line.replace(' MKT', ' MARKET')
            line = '%s %s%s' % (line, lines[1], extra)
            lines[:2] = [line]
        # look for trailing/leading ampersand
        elif lines[0].endswith(' &') or lines[1].startswith('& '):
            try:
                line = ' '.join(lines[:2]) + ' '
                line = line.replace(' MKT ', ' MARKET ').strip()
                lines[:2] = [line]
            except:
                error(lines, border='lined')
                raise
        # look for trailing/leading OF
        elif lines[0].endswith(' OF') and not lines[0].endswith('TOWN OF') or lines[1].startswith('OF '):
            if lines[1].startswith('CANADA,'):
                lines.insert(1, 'CANADA')
                lines[2] = lines[2][8:]
            line = ' '.join(lines[:2])
            lines[:2] = [line]
    name = lines[0:1]
    lines = lines[1:]
    # now check if first two of the remaining lines can be combined
    if len(lines) > 1 and (lines[0].endswith(' &') or lines[1].startswith('& ')):
        lines[0] = '%s %s' % (lines[0], lines.pop(1))
    return name, ignore, lines

def smart_upper(string):
    words = string.split()
    string = ' '.join(words)
    if string.isupper() or string.islower() or string == string.title():
        return string.upper()
    # mixed case
    final = []
    for word in words:
        if word.isupper() or word.islower() or word == word.title() or word.startswith('Mc'):
            final.append(word.upper())
        else:
            final.append(word)
    return ' '.join(final)

class TokenAddress(NamedTuple):
    address = 0, "address tuple"
    input = 1, "original line"
    tokens = 2, "tokens tuple"
    valid = 3, "address matches a valid token sequence"


def pfm(values):
    "prepare values dict for marshalling"
    result = {}
    for k, v in values.items():
        if not v:
            result[k] = False
        elif isinstance(v, Date):
            result[k] = v.strftime(DEFAULT_SERVER_DATE_FORMAT)
        elif isinstance(v, IDEquality):
            result[k] = v.id
        elif isinstance(v, ValueEquality):
            result[k] = v.value
        elif isinstance(v, PostalCode):
            result[k] = v.code
        elif isinstance(v, Enum):
            result[k] = v.value
        else:
            result[k] = v
    return result

def close_enough(old_rec, new_rec):
    # if float values are close enough, copy the old one to the new one
    for field_name in old_rec.keys():
        old_value = old_rec[field_name]
        new_value = new_rec[field_name]
        ov_is_float = isinstance(old_value, float)
        nv_is_float = isinstance(new_value, float)
        if ov_is_float and nv_is_float:
            if old_value - 0.000001 <= new_value <= old_value + 0.000001:
                new_rec[field_name] = old_value
    # now compare to see if equal
    if old_rec != new_rec:
        return False
    return True

def combine_by_value(old_records, new_records):
    all_keys = set(old_records.keys() + new_records.keys())
    changed_map = defaultdict(list)
    for key in all_keys:
        old_rec = old_records[key]
        new_rec = new_records[key]
        rec_key = []
        for oe_field, new_value in new_rec.items():
            if oe_field in ['xml_id', 'module', 'id']:
                continue
            old_value = old_rec[oe_field]
            if old_value != new_value:
                if isinstance(new_value, list):
                    new_value = tuple(new_value)
                rec_key.append((oe_field, new_value))
        if rec_key:
            changed_map[tuple(rec_key)].append(new_rec)
    return changed_map

def compare_records(old_records, new_records, ignore=lambda r: False):
    # get changed records as list of
    # (old_record, new_record, [(enum_schema_member, old_value, new_value), (...), ...]) tuples
    changes = []
    added = []
    deleted = []
    old_records_map = {}
    new_records_map = {}
    for rec in old_records:
        key = rec.module, rec.xml_id
        old_records_map[key] = rec
    for rec in new_records:
        key = rec.module, rec.xml_id
        new_records_map[key] = rec
    all_recs = set(new_records_map.keys() + old_records_map.keys())
    for key in all_recs:
        changed_values = []
        new_rec = new_records_map.get(key)
        old_rec = old_records_map.get(key)
        if new_rec == old_rec:
            continue
        if new_rec is None:
            deleted.append(old_rec)
            continue
        if old_rec is None:
            added.append(new_rec)
            continue
        if ignore(new_rec):
            continue
        assert set(new_rec.keys()) == set(old_rec.keys()), 'key mismatch'
        for field in new_rec.keys():
            new_value = new_rec[field]
            old_value = old_rec[field]
            if (new_value or old_value) and new_value != old_value:
                changed_values.append((field, old_rec[field], new_rec[field]))
        if changed_values:
            changes.append((old_rec, new_rec, changed_values))
    return changes, added, deleted


class Model(object):

    models = []
    errors = defaultdict(list)

    def __init__(self, table, abbr, module, context, raise_on_exception=False):
        self.models.append(self)
        self.table = table
        self.abbr = abbr
        self.module = module
        self.context = context
        self.raise_on_exception = raise_on_exception

    def __getattr__(self, name):
        return getattr(self.table, name)

    def error(self, msg):
        self.errors[self.abbr].append(msg)

    def create(self, key, values, context=None):
        if context is None:
            context = self.context
        try:
            return self.table.create(pfm(values), context=context)
        except Exception:
            cls, exc, tb = exc_info()
            self.errors[self.abbr].append('FIS ID %s:%s create with\n%r\n caused exception\n%s' % (self.module, key, values, exc))
            if self.raise_on_exception:
                raise
            return False

    def delete(self, ids, context=None):
        if context is None:
            context = self.context
        try:
            return self.table.unlink(ids)
        except Exception:
            cls, exc, tb = exc_info()
            self.errors[self.abbr].append('%s: deleting ID(s) %s caused exception %r' % (self.module, ', '.join([str(n) for n in ids]), exc))
            if self.raise_on_exception:
                raise
            return False

    unlink = delete

    def read(self, **kwds):
        if 'context' not in kwds:
            kwds['context'] = self.context
        return get_records(self.table, **kwds)

    def search(self, domain, context=None):
        if context is None:
            context = self.context
        return self.table.search(domain, context=context)

    def write(self, key, ids, values, context=None):
        if context is None:
            context = self.context
        try:
            print('writing to %s using %s\n and %s' % (ids, pfm(values), context), border='box', verbose=3)
            self.table.write(ids, pfm(values), context=context)
            return True
        except Exception:
            cls, exc, tb = exc_info()
            self.errors[self.abbr].append('FIS ID %s:%s write with\n%r\ncaused exception\n%s' % (self.module, key, values, exc))
            if self.raise_on_exception:
                raise
            return False


class FISenum(str, Enum):

    _init_ = 'value sequence'
    _order_ = lambda m: m.sequence

    FIS_names = LazyClassAttr(set)
    FIS_sequence = LazyClassAttr(dict)

    def __new__(cls, value, sequence):
        enum = str.__new__(cls, value)
        enum._value_ = value
        if '(' in value:
            fis_name, segment = value.split('(', 1)
            segment = segment.strip(' )')
        else:
            fis_name = value
            segment = None
        enum._value_ = value
        enum.fis_name = fis_name
        enum.segment = segment
        enum.sequence = sequence
        cls.FIS_names.add(fis_name)
        cls.FIS_sequence[sequence] = enum
        return enum

    def __repr__(self):
        return "<%s.%s>" % (self.__class__.__name__, self._name_)

    @classmethod
    def _missing_name_(cls, sequence):
        try:
            return cls.FIS_sequence[sequence]
        except KeyError:
            raise AttributeError('unable to find sequence %r in %r' % (sequence, cls.FIS_sequence))


class allow_exception(object):

    def __init__(self, *allowed):
        self.allowed = allowed

    def __enter__(self):
        return self

    def __exit__(self, cls, exc, tb):
        if isinstance(exc, self.allowed):
            # print error for future reference
            error(''.join(format_exception(*exc_info())).strip(), border='box')
            return True
        return False


class ProductLabelDescription(object):

    ingredients_text = ''
    recipe_text = ''

    def __init__(self, item_code, label_dir='/mnt/labeltime/Labels'):
        self.item_code = item_code
        self.label_dir = label_dir
        self.process()

    def label_text(self, label_type, leadin):
        lines = [
                line.strip()
                for line in open(self.label_file(label_type), 'rb').read().split("\r")
                if re.match(leadin, line) and line[15:].strip()
                ]
        return lines

    def label_file(self, label_type):
        filename = r'%s/%s/%s%s.spl' % (self.label_dir, self.item_code, self.item_code, label_type)
        if label_type.upper() == 'CC' and os.path.isfile("%so-r-i-g" % filename):
            return "%so-r-i-g" % filename
        if os.path.isfile(filename):
            return filename
        return filename        

    def process(self):
        try:
            lines = self.label_text('B',".91100")
        except IOError as exc1:
            try:
                lines = self.label_text('TT',".91100")
            except IOError as exc2:
                lines = []
                if exc1.errno not in (errno.ENOENT, errno.ENOTDIR):   # no such file or directory / not a directory
                    warnings.warn('item %r: %s' % (self.item_code, exc1))
                elif exc2.errno not in (errno.ENOENT, errno.ENOTDIR):
                    warnings.warn('item %r: %s' % (self.item_code, exc1))
        lines.sort()
        found = None
        self.ingredients = []
        self.ingredientLines = []
        for line in lines:
            if line[15:].startswith("INGREDIENTS:"):
                found = line[:7]
            if line[:7] == found:
                txt = line[15:]
                self.ingredients.append(txt)
                self.ingredientLines.append(line)
        ingr_text = []
        instr_text = []
        target = ingr_text
        for fragment in self.ingredients:
            for sentinel in recipe_sentinels:
                if re.match(sentinel, fragment, re.I):
                    target = instr_text
                    break
            else:
                for sentinal in new_line_sentinels:
                    if re.match(sentinal, fragment, re.I):
                        target.append('\n')
                        break
                else:
                    target.append(' ')
            target.append(fragment)
        ingr_text = ''.join(ingr_text)
        instr_text = ''.join(instr_text)
        self.ingredients_text = ingr_text.strip().replace('\xac', ' ')
        self.recipe_text = instr_text.strip().replace('\xac', ' ')
        return self.ingredients_text


def get_next_filename(name, limit=99):
    """
    adds numbers to file name until succesfully opened; stops at limit
    """
    file = Path(name)
    for i in range(10000):
        try:
            target = file.parent / file.base + '.%02d' % i + file.ext
            fh = os.open(target, os.O_CREAT | os.O_EXCL)
            os.close(fh)
            return target
        except OSError:
            pass
    else:
        raise IOError('unable to create file for %s' % name)


recipe_sentinels = (
        'Cooking',
        'COOKING',
        'DIRECTIONS',
        'INSTRUCTIONS',
        'RECIPE',
        'SUGGESTED',
        )

new_line_sentinels = (
        'ANTIOXIDANTS',
        'CONTAINS',
        'Manufactured',
        '\(May contain',
        'CAUTION',
        'COUNTRY',
        '[A-Z]+ MAY CONTAIN',
        'Product processed',
        '\d\d?%',
        
        )
def usps_street_suffix(word):
    return usps_street_suffix_abbr[usps_street_suffix_common[word]]

usps_street_suffix_common = {
    'ALLEE'      :  'ALLEY',
    'ALLEY'      :  'ALLEY',
    'ALLY'       :  'ALLEY',
    'ALY'        :  'ALLEY',
    'ANEX'       :  'ANNEX',
    'ANNEX'      :  'ANNEX',
    'ANNEX'      :  'ANNEX',
    'ANX'        :  'ANNEX',
    'ARC'        :  'ARCADE',
    'ARCADE'     :  'ARCADE',
    'AV'         :  'AVENUE',
    'AVE'        :  'AVENUE',
    'AVEN'       :  'AVENUE',
    'AVENU'      :  'AVENUE',
    'AVENUE'     :  'AVENUE',
    'AVN'        :  'AVENUE',
    'AVNUE'      :  'AVENUE',
    'BAYOO'      :  'BAYOO',
    'BAYOU'      :  'BAYOO',
    'BCH'        :  'BEACH',
    'BEACH'      :  'BEACH',
    'BEND'       :  'BEND',
    'BND'        :  'BEND',
    'BLF'        :  'BLUFF',
    'BLUF'       :  'BLUFF',
    'BLUFF'      :  'BLUFF',
    'BLUFFS'     :  'BLUFFS',
    'BOT'        :  'BOTTOM',
    'BOTTM'      :  'BOTTOM',
    'BOTTOM'     :  'BOTTOM',
    'BTM'        :  'BOTTOM',
    'BLVD'       :  'BOULEVARD',
    'BOUL'       :  'BOULEVARD',
    'BOULEVARD'  :  'BOULEVARD',
    'BOULV'      :  'BOULEVARD',
    'BR'         :  'BRANCH',
    'BRANCH'     :  'BRANCH',
    'BRNCH'      :  'BRANCH',
    'BRDGE'      :  'BRIDGE',
    'BRG'        :  'BRIDGE',
    'BRIDGE'     :  'BRIDGE',
    'BRK'        :  'BROOK',
    'BROOK'      :  'BROOK',
    'BROOKS'     :  'BROOKS',
    'BURG'       :  'BURG',
    'BURGS'      :  'BURGS',
    'BYP'        :  'BYPASS',
    'BYPA'       :  'BYPASS',
    'BYPAS'      :  'BYPASS',
    'BYPASS'     :  'BYPASS',
    'BYPS'       :  'BYPASS',
    'CAMP'       :  'CAMP',
    'CMP'        :  'CAMP',
    'CP'         :  'CAMP',
    'CANYN'      :  'CANYON',
    'CANYON'     :  'CANYON',
    'CNYN'       :  'CANYON',
    'CYN'        :  'CANYON',
    'CAPE'       :  'CAPE',
    'CPE'        :  'CAPE',
    'CAUSEWAY'   :  'CAUSEWAY',
    'CAUSWAY'    :  'CAUSEWAY',
    'CSWY'       :  'CAUSEWAY',
    'CEN'        :  'CENTER',
    'CENT'       :  'CENTER',
    'CENTER'     :  'CENTER',
    'CENTR'      :  'CENTER',
    'CENTRE'     :  'CENTER',
    'CNTER'      :  'CENTER',
    'CNTR'       :  'CENTER',
    'CTR'        :  'CENTER',
    'CENTERS'    :  'CENTERS',
    'CIR'        :  'CIRCLE',
    'CIRC'       :  'CIRCLE',
    'CIRCL'      :  'CIRCLE',
    'CIRCLE'     :  'CIRCLE',
    'CRCL'       :  'CIRCLE',
    'CRCLE'      :  'CIRCLE',
    'CIRCLES'    :  'CIRCLES',
    'CLF'        :  'CLIFF',
    'CLIFF'      :  'CLIFF',
    'CLFS'       :  'CLIFFS',
    'CLIFFS'     :  'CLIFFS',
    'CLB'        :  'CLUB',
    'CLUB'       :  'CLUB',
    'COMMON'     :  'COMMON',
    'COR'        :  'CORNER',
    'CORNER'     :  'CORNER',
    'CORNERS'    :  'CORNERS',
    'CORS'       :  'CORNERS',
    'COURSE'     :  'COURSE',
    'CRSE'       :  'COURSE',
    'COURT'      :  'COURT',
    'CRT'        :  'COURT',
    'CT'         :  'COURT',
    'COURTS'     :  'COURTS',
    'CTS'        :  'COURTS',
    'COVE'       :  'COVE',
    'CV'         :  'COVE',
    'COVES'      :  'COVES',
    'CK'         :  'CREEK',
    'CR'         :  'CREEK',
    'CREEK'      :  'CREEK',
    'CRK'        :  'CREEK',
    'CRECENT'    :  'CRESCENT',
    'CRES'       :  'CRESCENT',
    'CRESCENT'   :  'CRESCENT',
    'CRESENT'    :  'CRESCENT',
    'CRSCNT'     :  'CRESCENT',
    'CRSENT'     :  'CRESCENT',
    'CRSNT'      :  'CRESCENT',
    'CREST'      :  'CREST',
    'CROSSING'   :  'CROSSING',
    'CRSSING'    :  'CROSSING',
    'CRSSNG'     :  'CROSSING',
    'XING'       :  'CROSSING',
    'CROSSROAD'  :  'CROSSROAD',
    'CURVE'      :  'CURVE',
    'DALE'       :  'DALE',
    'DL'         :  'DALE',
    'DAM'        :  'DAM',
    'DM'         :  'DAM',
    'DIV'        :  'DIVIDE',
    'DIVIDE'     :  'DIVIDE',
    'DV'         :  'DIVIDE',
    'DVD'        :  'DIVIDE',
    'DR'         :  'DRIVE',
    'DRIV'       :  'DRIVE',
    'DRIVE'      :  'DRIVE',
    'DRV'        :  'DRIVE',
    'DRIVES'     :  'DRIVES',
    'EST'        :  'ESTATE',
    'ESTATE'     :  'ESTATE',
    'ESTATES'    :  'ESTATES',
    'ESTS'       :  'ESTATES',
    'EXP'        :  'EXPRESSWAY',
    'EXPR'       :  'EXPRESSWAY',
    'EXPRESS'    :  'EXPRESSWAY',
    'EXPRESSWAY' :  'EXPRESSWAY',
    'EXPW'       :  'EXPRESSWAY',
    'EXPY'       :  'EXPRESSWAY',
    'EXT'        :  'EXTENSION',
    'EXTENSION'  :  'EXTENSION',
    'EXTN'       :  'EXTENSION',
    'EXTNSN'     :  'EXTENSION',
    'EXTENSIONS' :  'EXTENSIONS',
    'EXTS'       :  'EXTENSIONS',
    'FALL'       :  'FALL',
    'FALLS'      :  'FALLS',
    'FLS'        :  'FALLS',
    'FERRY'      :  'FERRY',
    'FRRY'       :  'FERRY',
    'FRY'        :  'FERRY',
    'FIELD'      :  'FIELD',
    'FLD'        :  'FIELD',
    'FIELDS'     :  'FIELDS',
    'FLDS'       :  'FIELDS',
    'FLAT'       :  'FLAT',
    'FLT'        :  'FLAT',
    'FLATS'      :  'FLATS',
    'FLTS'       :  'FLATS',
    'FORD'       :  'FORD',
    'FRD'        :  'FORD',
    'FORDS'      :  'FORDS',
    'FOREST'     :  'FOREST',
    'FORESTS'    :  'FOREST',
    'FRST'       :  'FOREST',
    'FORG'       :  'FORGE',
    'FORGE'      :  'FORGE',
    'FRG'        :  'FORGE',
    'FORGES'     :  'FORGES',
    'FORK'       :  'FORK',
    'FRK'        :  'FORK',
    'FORKS'      :  'FORKS',
    'FRKS'       :  'FORKS',
    'FORT'       :  'FORT',
    'FRT'        :  'FORT',
    'FT'         :  'FORT',
    'FREEWAY'    :  'FREEWAY',
    'FREEWY'     :  'FREEWAY',
    'FRWAY'      :  'FREEWAY',
    'FRWY'       :  'FREEWAY',
    'FWY'        :  'FREEWAY',
    'GARDEN'     :  'GARDEN',
    'GARDN'      :  'GARDEN',
    'GDN'        :  'GARDEN',
    'GRDEN'      :  'GARDEN',
    'GRDN'       :  'GARDEN',
    'GARDENS'    :  'GARDENS',
    'GDNS'       :  'GARDENS',
    'GRDNS'      :  'GARDENS',
    'GATEWAY'    :  'GATEWAY',
    'GATEWY'     :  'GATEWAY',
    'GATWAY'     :  'GATEWAY',
    'GTWAY'      :  'GATEWAY',
    'GTWY'       :  'GATEWAY',
    'GLEN'       :  'GLEN',
    'GLN'        :  'GLEN',
    'GLENS'      :  'GLENS',
    'GREEN'      :  'GREEN',
    'GRN'        :  'GREEN',
    'GREENS'     :  'GREENS',
    'GROV'       :  'GROVE',
    'GROVE'      :  'GROVE',
    'GRV'        :  'GROVE',
    'GROVES'     :  'GROVES',
    'HARB'       :  'HARBOR',
    'HARBOR'     :  'HARBOR',
    'HARBR'      :  'HARBOR',
    'HBR'        :  'HARBOR',
    'HRBOR'      :  'HARBOR',
    'HARBORS'    :  'HARBORS',
    'HAVEN'      :  'HAVEN',
    'HAVN'       :  'HAVEN',
    'HVN'        :  'HAVEN',
    'HEIGHT'     :  'HEIGHTS',
    'HEIGHTS'    :  'HEIGHTS',
    'HGTS'       :  'HEIGHTS',
    'HT'         :  'HEIGHTS',
    'HTS'        :  'HEIGHTS',
    'HIGHWAY'    :  'HIGHWAY',
    'HIGHWY'     :  'HIGHWAY',
    'HIWAY'      :  'HIGHWAY',
    'HIWY'       :  'HIGHWAY',
    'HWAY'       :  'HIGHWAY',
    'HWY'        :  'HIGHWAY',
    'HILL'       :  'HILL',
    'HL'         :  'HILL',
    'HILLS'      :  'HILLS',
    'HLS'        :  'HILLS',
    'HLLW'       :  'HOLLOW',
    'HOLLOW'     :  'HOLLOW',
    'HOLLOWS'    :  'HOLLOW',
    'HOLW'       :  'HOLLOW',
    'HOLWS'      :  'HOLLOW',
    'INLET'      :  'INLET',
    'INLT'       :  'INLET',
    'IS'         :  'ISLAND',
    'ISLAND'     :  'ISLAND',
    'ISLND'      :  'ISLAND',
    'ISLANDS'    :  'ISLANDS',
    'ISLNDS'     :  'ISLANDS',
    'ISS'        :  'ISLANDS',
    'ISLE'       :  'ISLE',
    'ISLES'      :  'ISLE',
    'JCT'        :  'JUNCTION',
    'JCTION'     :  'JUNCTION',
    'JCTN'       :  'JUNCTION',
    'JUNCTION'   :  'JUNCTION',
    'JUNCTN'     :  'JUNCTION',
    'JUNCTON'    :  'JUNCTION',
    'JCTNS'      :  'JUNCTIONS',
    'JCTS'       :  'JUNCTIONS',
    'JUNCTIONS'  :  'JUNCTIONS',
    'KEY'        :  'KEY',
    'KY'         :  'KEY',
    'KEYS'       :  'KEYS',
    'KYS'        :  'KEYS',
    'KNL'        :  'KNOLL',
    'KNOL'       :  'KNOLL',
    'KNOLL'      :  'KNOLL',
    'KNLS'       :  'KNOLLS',
    'KNOLLS'     :  'KNOLLS',
    'LAKE'       :  'LAKE',
    'LK'         :  'LAKE',
    'LAKES'      :  'LAKES',
    'LKS'        :  'LAKES',
    'LAND'       :  'LAND',
    'LANDING'    :  'LANDING',
    'LNDG'       :  'LANDING',
    'LNDNG'      :  'LANDING',
    'LA'         :  'LANE',
    'LANE'       :  'LANE',
    'LANES'      :  'LANE',
    'LN'         :  'LANE',
    'LGT'        :  'LIGHT',
    'LIGHT'      :  'LIGHT',
    'LIGHTS'     :  'LIGHTS',
    'LF'         :  'LOAF',
    'LOAF'       :  'LOAF',
    'LCK'        :  'LOCK',
    'LOCK'       :  'LOCK',
    'LCKS'       :  'LOCKS',
    'LOCKS'      :  'LOCKS',
    'LDG'        :  'LODGE',
    'LDGE'       :  'LODGE',
    'LODG'       :  'LODGE',
    'LODGE'      :  'LODGE',
    'LOOP'       :  'LOOP',
    'LOOPS'      :  'LOOP',
    'MALL'       :  'MALL',
    'MANOR'      :  'MANOR',
    'MNR'        :  'MANOR',
    'MANORS'     :  'MANORS',
    'MNRS'       :  'MANORS',
    'MDW'        :  'MEADOW',
    'MEADOW'     :  'MEADOW',
    'MDWS'       :  'MEADOWS',
    'MEADOWS'    :  'MEADOWS',
    'MEDOWS'     :  'MEADOWS',
    'MEWS'       :  'MEWS',
    'MILL'       :  'MILL',
    'ML'         :  'MILL',
    'MILLS'      :  'MILLS',
    'MLS'        :  'MILLS',
    'MISSION'    :  'MISSION',
    'MISSN'      :  'MISSION',
    'MSN'        :  'MISSION',
    'MSSN'       :  'MISSION',
    'MOTORWAY'   :  'MOTORWAY',
    'MNT'        :  'MOUNT',
    'MOUNT'      :  'MOUNT',
    'MT'         :  'MOUNT',
    'MNTAIN'     :  'MOUNTAIN',
    'MNTN'       :  'MOUNTAIN',
    'MOUNTAIN'   :  'MOUNTAIN',
    'MOUNTIN'    :  'MOUNTAIN',
    'MTIN'       :  'MOUNTAIN',
    'MTN'        :  'MOUNTAIN',
    'MNTNS'      :  'MOUNTAINS',
    'MOUNTAINS'  :  'MOUNTAINS',
    'NCK'        :  'NECK',
    'NECK'       :  'NECK',
    'ORCH'       :  'ORCHARD',
    'ORCHARD'    :  'ORCHARD',
    'ORCHRD'     :  'ORCHARD',
    'OVAL'       :  'OVAL',
    'OVL'        :  'OVAL',
    'OVERPASS'   :  'OVERPASS',
    'PARK'       :  'PARK',
    'PK'         :  'PARK',
    'PRK'        :  'PARK',
    'PARKS'      :  'PARKS',
    'PARKWAY'    :  'PARKWAY',
    'PARKWY'     :  'PARKWAY',
    'PKWAY'      :  'PARKWAY',
    'PKWY'       :  'PARKWAY',
    'PKY'        :  'PARKWAY',
    'PARKWAYS'   :  'PARKWAYS',
    'PKWYS'      :  'PARKWAYS',
    'PASS'       :  'PASS',
    'PASSAGE'    :  'PASSAGE',
    'PATH'       :  'PATH',
    'PATHS'      :  'PATH',
    'PIKE'       :  'PIKE',
    'PIKES'      :  'PIKE',
    'PINE'       :  'PINE',
    'PINES'      :  'PINES',
    'PNES'       :  'PINES',
    'PL'         :  'PLACE',
    'PLACE'      :  'PLACE',
    'PLAIN'      :  'PLAIN',
    'PLN'        :  'PLAIN',
    'PLAINES'    :  'PLAINS',
    'PLAINS'     :  'PLAINS',
    'PLNS'       :  'PLAINS',
    'PLAZA'      :  'PLAZA',
    'PLZ'        :  'PLAZA',
    'PLZA'       :  'PLAZA',
    'POINT'      :  'POINT',
    'PT'         :  'POINT',
    'POINTS'     :  'POINTS',
    'PTS'        :  'POINTS',
    'PORT'       :  'PORT',
    'PRT'        :  'PORT',
    'PORTS'      :  'PORTS',
    'PRTS'       :  'PORTS',
    'PR'         :  'PRAIRIE',
    'PRAIRIE'    :  'PRAIRIE',
    'PRARIE'     :  'PRAIRIE',
    'PRR'        :  'PRAIRIE',
    'RAD'        :  'RADIAL',
    'RADIAL'     :  'RADIAL',
    'RADIEL'     :  'RADIAL',
    'RADL'       :  'RADIAL',
    'RAMP'       :  'RAMP',
    'RANCH'      :  'RANCH',
    'RANCHES'    :  'RANCH',
    'RNCH'       :  'RANCH',
    'RNCHS'      :  'RANCH',
    'RAPID'      :  'RAPID',
    'RPD'        :  'RAPID',
    'RAPIDS'     :  'RAPIDS',
    'RPDS'       :  'RAPIDS',
    'REST'       :  'REST',
    'RST'        :  'REST',
    'RDG'        :  'RIDGE',
    'RDGE'       :  'RIDGE',
    'RIDGE'      :  'RIDGE',
    'RDGS'       :  'RIDGES',
    'RIDGES'     :  'RIDGES',
    'RIV'        :  'RIVER',
    'RIVER'      :  'RIVER',
    'RIVR'       :  'RIVER',
    'RVR'        :  'RIVER',
    'RD'         :  'ROAD',
    'ROAD'       :  'ROAD',
    'RDS'        :  'ROADS',
    'ROADS'      :  'ROADS',
    'RT'         :  'ROUTE',
    'RTE'        :  'ROUTE',
    'ROUTE'      :  'ROUTE',
    'ROW'        :  'ROW',
    'RUE'        :  'RUE',
    'RUN'        :  'RUN',
    'SHL'        :  'SHOAL',
    'SHOAL'      :  'SHOAL',
    'SHLS'       :  'SHOALS',
    'SHOALS'     :  'SHOALS',
    'SHOAR'      :  'SHORE',
    'SHORE'      :  'SHORE',
    'SHR'        :  'SHORE',
    'SHOARS'     :  'SHORES',
    'SHORES'     :  'SHORES',
    'SHRS'       :  'SHORES',
    'SKYWAY'     :  'SKYWAY',
    'SPG'        :  'SPRING',
    'SPNG'       :  'SPRING',
    'SPRING'     :  'SPRING',
    'SPRNG'      :  'SPRING',
    'SPGS'       :  'SPRINGS',
    'SPNGS'      :  'SPRINGS',
    'SPRINGS'    :  'SPRINGS',
    'SPRNGS'     :  'SPRINGS',
    'SPUR'       :  'SPUR',
    'SPURS'      :  'SPURS',
    'SR'         :  'STATE ROUTE',
    'SQ'         :  'SQUARE',
    'SQR'        :  'SQUARE',
    'SQRE'       :  'SQUARE',
    'SQU'        :  'SQUARE',
    'SQUARE'     :  'SQUARE',
    'SQRS'       :  'SQUARES',
    'SQUARES'    :  'SQUARES',
    'ST RT'      :  'STATE ROUTE',
    'STA'        :  'STATION',
    'STATION'    :  'STATION',
    'STATN'      :  'STATION',
    'STN'        :  'STATION',
    'STRA'       :  'STRAVENUE',
    'STRAV'      :  'STRAVENUE',
    'STRAVE'     :  'STRAVENUE',
    'STRAVEN'    :  'STRAVENUE',
    'STRAVENUE'  :  'STRAVENUE',
    'STRAVN'     :  'STRAVENUE',
    'STRVN'      :  'STRAVENUE',
    'STRVNUE'    :  'STRAVENUE',
    'STREAM'     :  'STREAM',
    'STREME'     :  'STREAM',
    'STRM'       :  'STREAM',
    'ST'         :  'STREET',
    'STR'        :  'STREET',
    'STREET'     :  'STREET',
    'STRT'       :  'STREET',
    'STREETS'    :  'STREETS',
    'SMT'        :  'SUMMIT',
    'SUMIT'      :  'SUMMIT',
    'SUMITT'     :  'SUMMIT',
    'SUMMIT'     :  'SUMMIT',
    'TER'        :  'TERRACE',
    'TERR'       :  'TERRACE',
    'TERRACE'    :  'TERRACE',
    'THROUGHWAY' :  'THROUGHWAY',
    'TRACE'      :  'TRACE',
    'TRACES'     :  'TRACE',
    'TRCE'       :  'TRACE',
    'TRACK'      :  'TRACK',
    'TRACKS'     :  'TRACK',
    'TRAK'       :  'TRACK',
    'TRK'        :  'TRACK',
    'TRKS'       :  'TRACK',
    'TRAFFICWAY' :  'TRAFFICWAY',
    'TRFY'       :  'TRAFFICWAY',
    'TR'         :  'TRAIL',
    'TRAIL'      :  'TRAIL',
    'TRAILS'     :  'TRAIL',
    'TRL'        :  'TRAIL',
    'TRLS'       :  'TRAIL',
    'TUNEL'      :  'TUNNEL',
    'TUNL'       :  'TUNNEL',
    'TUNLS'      :  'TUNNEL',
    'TUNNEL'     :  'TUNNEL',
    'TUNNELS'    :  'TUNNEL',
    'TUNNL'      :  'TUNNEL',
    'TPK'        :  'TURNPIKE',
    'TPKE'       :  'TURNPIKE',
    'TRNPK'      :  'TURNPIKE',
    'TRPK'       :  'TURNPIKE',
    'TURNPIKE'   :  'TURNPIKE',
    'TURNPK'     :  'TURNPIKE',
    'UNDERPASS'  :  'UNDERPASS',
    'UN'         :  'UNION',
    'UNION'      :  'UNION',
    'UNIONS'     :  'UNIONS',
    'VALLEY'     :  'VALLEY',
    'VALLY'      :  'VALLEY',
    'VLLY'       :  'VALLEY',
    'VLY'        :  'VALLEY',
    'VALLEYS'    :  'VALLEYS',
    'VLYS'       :  'VALLEYS',
    'VDCT'       :  'VIADUCT',
    'VIA'        :  'VIADUCT',
    'VIADCT'     :  'VIADUCT',
    'VIADUCT'    :  'VIADUCT',
    'VIEW'       :  'VIEW',
    'VW'         :  'VIEW',
    'VIEWS'      :  'VIEWS',
    'VWS'        :  'VIEWS',
    'VILL'       :  'VILLAGE',
    'VILLAG'     :  'VILLAGE',
    'VILLAGE'    :  'VILLAGE',
    'VILLG'      :  'VILLAGE',
    'VILLIAGE'   :  'VILLAGE',
    'VLG'        :  'VILLAGE',
    'VILLAGES'   :  'VILLAGES',
    'VLGS'       :  'VILLAGES',
    'VILLE'      :  'VILLE',
    'VL'         :  'VILLE',
    'VIS'        :  'VISTA',
    'VIST'       :  'VISTA',
    'VISTA'      :  'VISTA',
    'VST'        :  'VISTA',
    'VSTA'       :  'VISTA',
    'WALK'       :  'WALK',
    'WALKS'      :  'WALKS',
    'WALL'       :  'WALL',
    'WAY'        :  'WAY',
    'WY'         :  'WAY',
    'WAYS'       :  'WAYS',
    'WELL'       :  'WELL',
    'WELLS'      :  'WELLS',
    'WLS'        :  'WELLS',
    }

usps_street_suffix_abbr = {
    'ALLEY'      :  'ALY',
    'ANNEX'      :  'ANX',
    'ARCADE'     :  'ARC',
    'AVENUE'     :  'AVE',
    'BAYOO'      :  'BYU',
    'BEACH'      :  'BCH',
    'BEND'       :  'BND',
    'BLUFF'      :  'BLF',
    'BLUFFS'     :  'BLFS',
    'BOTTOM'     :  'BTM',
    'BOULEVARD'  :  'BLVD',
    'BRANCH'     :  'BR',
    'BRIDGE'     :  'BRG',
    'BROOK'      :  'BRK',
    'BROOKS'     :  'BRKS',
    'BURG'       :  'BG',
    'BURGS'      :  'BGS',
    'BYPASS'     :  'BYP',
    'CAMP'       :  'CP',
    'CANYON'     :  'CYN',
    'CAPE'       :  'CPE',
    'CAUSEWAY'   :  'CSWY',
    'CENTER'     :  'CTR',
    'CENTERS'    :  'CTRS',
    'CIRCLE'     :  'CIR',
    'CIRCLES'    :  'CIRS',
    'CLIFF'      :  'CLF',
    'CLIFFS'     :  'CLFS',
    'CLUB'       :  'CLB',
    'COMMON'     :  'CMN',
    'CORNER'     :  'COR',
    'CORNERS'    :  'CORS',
    'COURSE'     :  'CRSE',
    'COURT'      :  'CT',
    'COURTS'     :  'CTS',
    'COVE'       :  'CV',
    'COVES'      :  'CVS',
    'CREEK'      :  'CRK',
    'CRESCENT'   :  'CRES',
    'CREST'      :  'CRST',
    'CROSSING'   :  'XING',
    'CROSSROAD'  :  'XRD',
    'CURVE'      :  'CURV',
    'DALE'       :  'DL',
    'DAM'        :  'DM',
    'DIVIDE'     :  'DV',
    'DRIVE'      :  'DR',
    'DRIVES'     :  'DRS',
    'ESTATE'     :  'EST',
    'ESTATES'    :  'ESTS',
    'EXPRESSWAY' :  'EXPY',
    'EXTENSION'  :  'EXT',
    'EXTENSIONS' :  'EXTS',
    'FALL'       :  'FALL',
    'FALLS'      :  'FLS',
    'FERRY'      :  'FRY',
    'FIELD'      :  'FLD',
    'FIELDS'     :  'FLDS',
    'FLAT'       :  'FLT',
    'FLATS'      :  'FLTS',
    'FORD'       :  'FRD',
    'FORDS'      :  'FRDS',
    'FOREST'     :  'FRST',
    'FORGE'      :  'FRG',
    'FORGES'     :  'FRGS',
    'FORK'       :  'FRK',
    'FORKS'      :  'FRKS',
    'FORT'       :  'FT',
    'FREEWAY'    :  'FWY',
    'GARDEN'     :  'GDN',
    'GARDENS'    :  'GDNS',
    'GATEWAY'    :  'GTWY',
    'GLEN'       :  'GLN',
    'GLENS'      :  'GLNS',
    'GREEN'      :  'GRN',
    'GREENS'     :  'GRNS',
    'GROVE'      :  'GRV',
    'GROVES'     :  'GRVS',
    'HARBOR'     :  'HBR',
    'HARBORS'    :  'HBRS',
    'HAVEN'      :  'HVN',
    'HEIGHTS'    :  'HTS',
    'HIGHWAY'    :  'HWY',
    'HILL'       :  'HL',
    'HILLS'      :  'HLS',
    'HOLLOW'     :  'HOLW',
    'INLET'      :  'INLT',
    'ISLAND'     :  'IS',
    'ISLANDS'    :  'ISS',
    'ISLE'       :  'ISLE',
    'JUNCTION'   :  'JCT',
    'JUNCTIONS'  :  'JCTS',
    'KEY'        :  'KY',
    'KEYS'       :  'KYS',
    'KNOLL'      :  'KNL',
    'KNOLLS'     :  'KNLS',
    'LAKE'       :  'LK',
    'LAKES'      :  'LKS',
    'LAND'       :  'LAND',
    'LANDING'    :  'LNDG',
    'LANE'       :  'LN',
    'LIGHT'      :  'LGT',
    'LIGHTS'     :  'LGTS',
    'LOAF'       :  'LF',
    'LOCK'       :  'LCK',
    'LOCKS'      :  'LCKS',
    'LODGE'      :  'LDG',
    'LOOP'       :  'LOOP',
    'MALL'       :  'MALL',
    'MANOR'      :  'MNR',
    'MANORS'     :  'MNRS',
    'MEADOW'     :  'MDW',
    'MEADOWS'    :  'MDWS',
    'MEWS'       :  'MEWS',
    'MILL'       :  'ML',
    'MILLS'      :  'MLS',
    'MISSION'    :  'MSN',
    'MOTORWAY'   :  'MTWY',
    'MOUNT'      :  'MT',
    'MOUNTAIN'   :  'MTN',
    'MOUNTAINS'  :  'MTNS',
    'NECK'       :  'NCK',
    'ORCHARD'    :  'ORCH',
    'OVAL'       :  'OVAL',
    'OVERPASS'   :  'OPAS',
    'PARK'       :  'PARK',
    'PARKS'      :  'PRKS',
    'PARKWAY'    :  'PKWY',
    'PASS'       :  'PASS',
    'PASSAGE'    :  'PSGE',
    'PATH'       :  'PATH',
    'PIKE'       :  'PIKE',
    'PINE'       :  'PNE',
    'PINES'      :  'PNES',
    'PLACE'      :  'PL',
    'PLAIN'      :  'PLN',
    'PLAINS'     :  'PLNS',
    'PLAZA'      :  'PLZ',
    'POINT'      :  'PT',
    'POINTS'     :  'PTS',
    'PORT'       :  'PRT',
    'PORTS'      :  'PRTS',
    'PRAIRIE'    :  'PR',
    'RADIAL'     :  'RADL',
    'RAMP'       :  'RAMP',
    'RANCH'      :  'RNCH',
    'RAPID'      :  'RPD',
    'RAPIDS'     :  'RPDS',
    'REST'       :  'RST',
    'RIDGE'      :  'RDG',
    'RIDGES'     :  'RDGS',
    'RIVER'      :  'RIV',
    'ROAD'       :  'RD',
    'ROADS'      :  'RDS',
    'ROUTE'      :  'RTE',
    'ROW'        :  'ROW',
    'RUE'        :  'RUE',
    'RUN'        :  'RUN',
    'SHOAL'      :  'SHL',
    'SHOALS'     :  'SHLS',
    'SHORE'      :  'SHR',
    'SHORES'     :  'SHRS',
    'SKYWAY'     :  'SKWY',
    'SPRING'     :  'SPG',
    'SPRINGS'    :  'SPGS',
    'SPUR'       :  'SPUR',
    'SQUARE'     :  'SQ',
    'SQUARES'    :  'SQS',
    'STATE ROUTE':  'STATE ROUTE',
    'STATION'    :  'STA',
    'STRAVENUE'  :  'STRA',
    'STREAM'     :  'STRM',
    'STREET'     :  'ST',
    'STREETS'    :  'STS',
    'SUMMIT'     :  'SMT',
    'TERRACE'    :  'TER',
    'THROUGHWAY' :  'TRWY',
    'TRACE'      :  'TRCE',
    'TRACK'      :  'TRAK',
    'TRAFFICWAY' :  'TRFY',
    'TRAIL'      :  'TRL',
    'TUNNEL'     :  'TUNL',
    'TURNPIKE'   :  'TPKE',
    'UNDERPASS'  :  'UPAS',
    'UNION'      :  'UN',
    'UNIONS'     :  'UNS',
    'VALLEY'     :  'VLY',
    'VALLEYS'    :  'VLYS',
    'VIADUCT'    :  'VIA',
    'VIEW'       :  'VW',
    'VIEWS'      :  'VWS',
    'VILLAGE'    :  'VLG',
    'VILLAGES'   :  'VLGS',
    'VILLE'      :  'VL',
    'VISTA'      :  'VIS',
    'WALK'       :  'WALK',
    'WALKS'      :  'WALKS',
    'WALL'       :  'WALL',
    'WAY'        :  'WAY',
    'WAYS'       :  'WAYS',
    'WELL'       :  'WL',
    'WELLS'      :  'WLS',
    }

usps_secondary = {
    'APARTMENT'  :  'APT',
    'APT'        :  'APT',
    'BASEMENT'   :  'BSMT',
    'BSMT'       :  'BSMT',
    'BOX'        :  'BOX',
    'BUILDING'   :  'BLDG',
    'BLDG'       :  'BLDG',
    'DEPARTMENT' :  'DEPT',
    'DEPT'       :  'DEPT',
    'FLOOR'      :  'FLOOR',
    'FLR'        :  'FLOOR',
    'FL'         :  'FLOOR',
    'FRONT'      :  'FRONT',
    'FRNT'       :  'FRONT',
    'HANGER'     :  'HNGR',
    'HNGR'       :  'HNGR',
    'KEY'        :  'KEY',
    'KEY'        :  'KEY',
    'LOBBY'      :  'LOBBY',
    'LBBY'       :  'LOBBY',
    'LOT'        :  'LOT',
    'LOWER'      :  'LOWER',
    'LOWR'       :  'LOWER',
    'OFFICE'     :  'OFC',
    'OFC'        :  'OFC',
    'PENTHOUSE'  :  'PH',
    'PH'         :  'PH',
    'PIER'       :  'PIER',
    'REAR'       :  'REAR',
    'ROOM'       :  'RM',
    'RM'         :  'RM',
    'SIDE'       :  'SIDE',
    'SLIP'       :  'SLIP',
    'SLIP'       :  'SLIP',
    'SPACE'      :  'SPC',
    'SPC'        :  'SPC',
    'STOP'       :  'STOP',
    'SUITE'      :  'STE',
    'STE'        :  'STE',
    'TRAILER'    :  'TRLR',
    'TRLR'       :  'TRLR',
    'UNIT'       :  'UNIT',
    'UPPER'      :  'UPPER',
    'UPPR'       :  'UPPER',
    '#'          :  '#',
    }

