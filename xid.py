"various OpenERP routines"

def get_xml_ids(obj, cr, uid, ids, name=None, arg=None, context=None):
    imd = obj.pool.get('ir.model.data')
    result = {}
    for id in ids:
        try:
            res = imd.get_object_from_model_resid(
                    cr,
                    uid,
                    obj._name,
                    id,
                    context=context,
                    )
        except ValueError:
            result[id] = ''
        else:
            result[id] = res['name']
    return result


def search_xml_id(obj, cr, uid, model, name, domain, context=None):
    """
    domain[0][0] = 'xml_id'
    domain[0][1] = 'ilike', 'not ilike', '=', '!='
    domain[0][2] = 'some text to compare against'
    """
    if not len(domain):
        return []
    if not context:
        context = {}
    imd = obj.pool.get('ir.model.data')
    records = imd._get_model_records(cr, uid, obj._name)
    (field, op, text) ,= domain
    itext = text.lower()
    if op == 'ilike':
        id_names = [(r['res_id'], r['name']) for r in records if itext in r['name'].lower()]
    elif op == 'not ilike':
        id_names = [(r['res_id'], r['name']) for r in records if itext not in r['name'].lower()]
    elif op == '=':
        id_names = [(r['res_id'], r['name']) for r in records if text == r['name']]
    elif op == '!=':
        id_names = [(r['res_id'], r['name']) for r in records if text != r['name']]
    else:
        raise ValueError('invalid op for external_id: %s' % op)
    return [('id', 'in', [x[0] for x in id_names])]


def update_xml_id(obj, cr, uid, id, field, value, model, context=None):
    imd = obj.pool.get('ir.model.data')
    if context is None:
        context = {}
    module = context.get('module', '')
    try:
        rec = imd.get_object_from_model_resid(cr, uid, model, id, context=context)
    except ValueError:
        imd.create(cr, uid, {'module':module, 'name':value, 'model':model, 'res_id':id, 'noupdate':True}, context=context)
    else:
        imd.write(cr, uid, rec['id'], {'module':module, 'name':value, 'model':model, 'res_id':id, 'noupdate':True}, context=context)
    return True
