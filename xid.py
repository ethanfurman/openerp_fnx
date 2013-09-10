"various OpenERP routines"

from fnx import check_company_settings


def get_xml_ids(obj, cr, uid, ids, name=None, fld_desc_err=None, context=None):
    """able to handle multiple records at once"""
    if context is None:
        context = {}
    if fld_desc_err is None:
        raise ValueError('FIS Integration setting must be specified')
    field, desc, error = fld_desc_err
    settings = check_company_settings(obj, cr, uid, fld_desc_err)
    module = settings[field]
    model = obj._name
    imd = obj.pool.get('ir.model.data')
    result = {}
    for id in ids:
        try:
            res = imd.get_object_from_module_model_resid(
                    cr, uid,
                    module, model, id,
                    context=context,
                    )
        except ValueError:
            result[id] = ''
        else:
            result[id] = res['name']
    return result

def update_xml_id(obj, cr, uid, id, field_name, field_value, fld_desc_err, context=None):
    """one record at a time"""
    if context is None:
        context = {}
    if fld_desc_err is None:
        raise ValueError('FIS Integration setting must be specified')
    field, desc, error = fld_desc_err
    settings = check_company_settings(obj, cr, uid, fld_desc_err)
    module = settings[field]
    model = obj._name
    imd = obj.pool.get('ir.model.data')
    try:
        rec = imd.get_object_from_module_model_resid(cr, uid, module, model, id, context=context)
    except ValueError:
        imd.create(cr, uid, {'module':module, 'model':model, 'res_id':id, 'name':field_value, 'noupdate':True}, context=context)
    else:
        imd.write(cr, uid, rec.id, {'module':module, 'model':model, 'res_id':id, 'name':field_value, 'noupdate':True}, context=context)
    return True

def search_xml_id(obj, cr, uid, module, name, domain, fld_desc_err=None, context=None):
    """
    domain[0][0] = 'xml_id'
    domain[0][1] = 'ilike', 'not ilike', '=', '!='
    domain[0][2] = 'some text to compare against'
    """
    if not len(domain):
        return []
    if not context:
        context = {}
    if fld_desc_err is None:
        raise ValueError('FIS Integration setting must be specified')
    field, desc, error = fld_desc_err
    settings = check_company_settings(obj, cr, uid, fld_desc_err)
    module = settings[field]
    imd = obj.pool.get('ir.model.data')
    records = imd._get_model_records(cr, uid, obj._name)
    (field, op, text) ,= domain
    itext = text.lower()
    if op == 'ilike':
        id_names = [(r.res_id, r.name) for r in records if itext in r.name.lower() and r.module == module]
    elif op == 'not ilike':
        id_names = [(r.res_id, r.name) for r in records if itext not in r.name.lower() and r.module == module]
    elif op == '=':
        id_names = [(r.res_id, r.name) for r in records if text == r.name and r.module == module]
    elif op == '!=':
        id_names = [(r.res_id, r.name) for r in records if text != r.name and r.module == module]
    else:
        raise ValueError('invalid op for external_id: %s' % op)
    return [('id', 'in', [x[0] for x in id_names])]


