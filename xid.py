"various OpenERP routines related to exposing fis ids stored in xml_id in ir.model.data"

from collections import defaultdict
from osv.osv import except_osv as ERPError
from openerp import tools, SUPERUSER_ID

class xmlid(object):

    def create(self, cr, uid, values, context=None):
        xml_id = values.pop('xml_id', None)
        module = values.pop('module', None)
        if sum(1 for k in (xml_id, module) if k) == 1:
            raise ERPError('Error', 'if one of (xml_id, module) is set, both must be (%r, %r)' % (xml_id, module))
        new_id = super(xmlid, self).create(cr, uid, values, context=context)
        if xml_id and module:
            imd = self.pool.get('ir.model.data')
            # check for orphaned xml_ids
            orphan = imd.search(cr, uid, [('name','=',xml_id),('module','=',module),('model','=',self._name)])
            if orphan:
                # actually an orphan?
                found = imd.browse(cr, uid, orphan[0], context=context)
                record = self.browse(cr, uid, found.res_id, context=context)
                if record:
                    # duplicates not allowed!
                    raise ERPError('Error', '%s:%s belongs to %s' % (module, xml_id, record.name))
                else:
                    imd.write(cr, uid, orphan[0], {'res_id':new_id}, context=context)
            else:
                imd.create(cr, uid, {'module':module, 'name':xml_id, 'model':self._name, 'res_id':new_id}, context=context)
        return new_id

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=100):
        result = super(xmlid, self).name_search(cr, uid, name=name, args=args, operator=operator, context=context, limit=limit)
        if not args:
            args = []
        ns_result = []
        if name:
            ids = self.search(cr, uid, [('xml_id','ilike',name.upper())] + args, limit=limit, context=context)
            if ids:
                ns_result = self.name_get(cr, uid, ids, context=context)
        return list(set(result + ns_result))

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        # print 'xmlid.search(uid=%r, args=%r, context=%r' % (uid, args, context)
        return super(xmlid, self).search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def write(self, cr, uid, ids, values, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        xml_id = values.pop('xml_id', None)
        module = values.pop('module', None)
        given = sum(1 for k in (xml_id, module) if k)
        if given == 1:
            raise ERPError('Error', 'if one of (xml_id, module) is set, both must be (%r, %r)' % (xml_id, module))
        if given == 2:
            if len(ids) > 1:
                raise ERPError('Error', '(xml_id, module) pairs, if given, must be unique per record')
            imd = self.pool.get('ir.model.data')
            try:
                record = imd.get_object_from_model_resid(cr, uid, model=self._name, res_id=ids[0])
                imd.write(cr, uid, record.id, {'module':module, 'name':xml_id}, context=context)
            except ValueError:
                imd.create(cr, uid, {'model':self._name, 'res_id':ids[0], 'module':module, 'name':xml_id}, context=context)
        super(xmlid, self).write(cr, uid, ids, values, context=context)
        self.clear_caches()
        return True

    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        result = super(xmlid, self).unlink(cr, uid, ids, context=context)
        imd = self.pool.get('ir.model.data')
        for record in self.browse(cr, uid, ids, context=context):
            xml_id = record.xml_id or ''
            module = record.module or ''
            for orphan in imd.search(cr, uid, [('name','=',xml_id),('module','=',module)], context=context):
                imd.unlink(cr, uid, orphan.id, context=context)
        self.clear_caches()
        return result

    def clear_caches(self):
        self._get_xml_ids.clear_cache(self)
        self._search_xml_id.clear_cache(self)
        return self

    def get_xml_ids(self, cr, uid, ids, field_names, arg, context=None):
        "wrapper for self._get_xml_ids"
        return self._get_xml_ids(cr, uid, tuple(ids), tuple(field_names), arg)

    @tools.ormcache(skiparg=3)
    def _get_xml_ids(self, cr, uid, ids, field_names, arg):
        """
        Return {id: {'module':..., 'xml_id':...}} for each id in ids

        It is entirely possible that any given model/res_id will have more than one
        module/name match, but we only return matches where module equals the module
        we're looking for; otherwise we return False.

        arg = (module_name1, module_name2, ..., module_nameN)
        """
        modules = set(arg or '')
        model = self._name
        imd = self.pool.get('ir.model.data')
        result = defaultdict(dict)
        imd_records = {}
        for rec in imd.get_model_records(cr, uid, model):
            imd_records[rec.res_id] = rec
        for id in ids:
            rec = imd_records.get(id)
            if rec is not None and rec.module in modules:
                    result[id]['xml_id'] = rec.name
                    result[id]['module'] = rec.module
            else:
                result[id]['xml_id'] = False
                result[id]['module'] = False
        return dict(result)

    def update_xml_id(self, cr, uid, id, field_name, field_value, arg, context=None):
        "one record at a time"
        if not field_value:
            raise ERPError('Error', 'Empty values are not allowed for field %r' % field_name)
        if field_name == 'xml_id':
            field_name = 'name'
        model = self._name
        imd = self.pool.get('ir.model.data')
        rec = imd.get_object_from_model_resid(cr, uid, model, id)
        imd.write(cr, uid, rec.id, {field_name:field_value})
        self.clear_caches()
        return True

    def search_xml_id(self, cr, uid, obj_again, field_name, domain, context=None):
        "wrapper for _search_xml_id"
        return self._search_xml_id(cr, uid, obj_again, field_name, tuple(domain))

    @tools.ormcache(skiparg=3)
    def _search_xml_id(self, cr, uid, obj_again, field_name, domain):
        """
        domain[0][0] = 'xml_id'
        domain[0][1] = 'ilike', 'not ilike', '=', '!='
        domain[0][2] = 'some text to compare against'
        """
        if not domain:
            return []
        if field_name == 'xml_id':
            field_name = 'name'
        imd = self.pool.get('ir.model.data')
        model = self._name
        records = imd.get_model_records(cr, SUPERUSER_ID, model)
        (field, op, text) ,= domain
        if isinstance(text, (str, unicode)):
            itext = text.lower()
        elif isinstance(text, bool):
            id_names = [(r.res_id, r[field_name]) for r in records]
            if op == '=':
                return [('id', 'not in', [x[0] for x in id_names])]
            else:
                return [('id', 'in', [x[0] for x in id_names])]
        if op == 'ilike':
            id_names = [(r.res_id, r[field_name]) for r in records if itext in r[field_name].lower()]
        elif op == 'not ilike':
            id_names = [(r.res_id, r[field_name]) for r in records if itext not in r[field_name].lower()]
        elif op == '=':
            id_names = [(r.res_id, r[field_name]) for r in records if text == r[field_name]]
        elif op == '!=':
            id_names = [(r.res_id, r[field_name]) for r in records if text != r[field_name]]
        elif op == 'in':
            id_names = [(r.res_id, r[field_name]) for r in records if r[field_name] in text]
        elif op == 'not in':
            id_names = [(r.res_id, r[field_name]) for r in records if r[field_name] not in text]
        else:
            raise ValueError('invalid op for external_id: %s' % op)
        return [('id', 'in', [x[0] for x in id_names])]

def get_xml_ids(obj, cr, uid, ids, field_names, arg, context=None):
    """
    Return {id: {'module':..., 'xml_id':...}} for each id in ids

    It is entirely possible that any given model/res_id will have more than one
    module/name match, but we only return matches where module equals the module
    we're looking for; otherwise we return ''.

    arg = (module_name1, module_name2, ..., module_nameN)
    """
    modules = set(arg or '')
    model = obj._name
    imd = obj.pool.get('ir.model.data')
    result = defaultdict(dict)
    imd_records = {}
    for rec in imd.get_model_records(cr, uid, model):
        imd_records[rec.res_id] = rec
    for id in ids:
        rec = imd_records.get(id)
        if rec is not None and rec.module in modules:
                result[id]['xml_id'] = rec.name
                result[id]['module'] = rec.module
        else:
            result[id]['xml_id'] = False
            result[id]['module'] = False
    return dict(result)

def update_xml_id(obj, cr, uid, id, field_name, field_value, arg):
    """one record at a time"""
    if not field_value:
        raise ERPError('Error', 'Empty values are not allowed for field %r' % field_name)
    if field_name == 'xml_id':
        field_name = 'name'
    model = obj._name
    imd = obj.pool.get('ir.model.data')
    rec = imd.get_object_from_model_resid(cr, uid, model, id)
    imd.write(cr, uid, rec.id, {field_name:field_value})
    return True

def search_xml_id(obj, cr, uid, obj_again, field_name, domain, context=None):
    """
    domain[0][0] = 'xml_id'
    domain[0][1] = 'ilike', 'not ilike', '=', '!='
    domain[0][2] = 'some text to compare against'
    """
    if not domain:
        return []
    if field_name == 'xml_id':
        field_name = 'name'
    imd = obj.pool.get('ir.model.data')
    model = obj._name
    records = imd.get_model_records(cr, uid, model)
    (field, op, text) ,= domain
    if isinstance(text, (str, unicode)):
        itext = text.lower()
    elif isinstance(text, bool):
        id_names = [(r.res_id, r[field_name]) for r in records]
        if op == '=':
            return [('id', 'not in', [x[0] for x in id_names])]
        else:
            return [('id', 'in', [x[0] for x in id_names])]
    if op == 'ilike':
        id_names = [(r.res_id, r[field_name]) for r in records if itext in r[field_name].lower()]
    elif op == 'not ilike':
        id_names = [(r.res_id, r[field_name]) for r in records if itext not in r[field_name].lower()]
    elif op == '=':
        id_names = [(r.res_id, r[field_name]) for r in records if text == r[field_name]]
    elif op == '!=':
        id_names = [(r.res_id, r[field_name]) for r in records if text != r[field_name]]
    elif op == 'in':
        id_names = [(r.res_id, r[field_name]) for r in records if r[field_name] in text]
    elif op == 'not in':
        id_names = [(r.res_id, r[field_name]) for r in records if r[field_name] not in text]
    else:
        raise ValueError('invalid op for external_id: %s' % op)
    return [('id', 'in', [x[0] for x in id_names])]


