"various OpenERP routines related to exposing fis ids stored in xml_id in ir.model.data"

from collections import defaultdict
from fnx import check_company_settings


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
    ids = set(ids)
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
            result[id]['xml_id'] = ''
            result[id]['module'] = ''
    return dict(result)

def update_xml_id(obj, cr, uid, id, field_name, field_value, arg, context=None):
    """one record at a time"""
    if not field_value:
        return True
        raise ValueError('Empty values are not allowed for field %r' % field_name)
    if context is None:
        context = {}
    if field_name == 'xml_id':
        field_name = 'name'
    model = obj._name
    imd = obj.pool.get('ir.model.data')
    try:
        rec = imd.get_object_from_model_resid(cr, uid, model, id, context=context)
    except ValueError:
        values = {'model':model, 'res_id':id, field_name:field_value}
        if field_name != 'name':
            values['name'] = ''
        imd.create(cr, uid, values, context=context)
    else:
        imd.write(cr, uid, rec.id, {field_name:field_value}, context=context)
    return True

def search_xml_id(obj, cr, uid, obj_again, field_name, domain, context=None):
    """
    domain[0][0] = 'xml_id'
    domain[0][1] = 'ilike', 'not ilike', '=', '!='
    domain[0][2] = 'some text to compare against'
    """
    if not len(domain):
        return []
    if field_name == 'xml_id':
        field_name = 'name'
    imd = obj.pool.get('ir.model.data')
    model = obj._name
    records = imd.get_model_records(cr, uid, model)
    (field, op, text) ,= domain
    if field == 'xml_id':
        field = 'name'
    if text:
        itext = text.lower()
    if op == 'ilike':
        id_names = [(r.res_id, r[field_name]) for r in records if itext in r[field_name].lower()]
    elif op == 'not ilike':
        id_names = [(r.res_id, r[field_name]) for r in records if itext not in r[field_name].lower()]
    elif op == '=' and text is False:
        print 'not set'
        id_names = [(r.res_id, r[field_name]) for r in records if r[field_name] is False or r.module not in modules]
        print id_names
    elif op == '=':
        id_names = [(r.res_id, r[field_name]) for r in records if text == r[field_name]]
    elif op == '!=':
        id_names = [(r.res_id, r[field_name]) for r in records if text != r[field_name]]
    elif op == 'in':
        print field_name
        print repr(text)
        id_names = [(r.res_id, r[field_name]) for r in records if r[field_name] in text]
        print (22133,'vnms') in id_names
        print id_names[:10]
    elif op == 'not in':
        id_names = [(r.res_id, r[field_name]) for r in records if r[field_name] not in text]
    else:
        raise ValueError('invalid op for external_id: %s' % op)
    return [('id', 'in', [x[0] for x in id_names])]


