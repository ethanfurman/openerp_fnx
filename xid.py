"various OpenERP routines related to exposing fis ids stored in xml_id in ir.model.data"

import logging

_logger = logging.getLogger(__name__)

class xmlid(object):

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            if name[0] == ' ':
                ids = self.search(cr, uid, [('xml_id','like',name.lstrip())]+ args, limit=limit, context=context)
            else:
                ids = self.search(cr, uid, [('xml_id','=like',name+'%')]+ args, limit=limit, context=context)
            if ids:
                return self.name_get(cr, uid, ids, context=context)
        return super(xmlid, self).name_search(cr, uid, name=name, args=args, operator=operator, context=context, limit=limit)

    def get_xml_id_map(self, cr, uid, module, ids=None, context=None):
        "return {xml_id: id} for all xml_ids in module"
        imd = self.pool.get('ir.model.data')
        result = {}
        for rec in imd.read(cr, uid, [('model','=',self._name),('module','=',module)], fields=['name','res_id'], context=context):
            if ids is None or rec['res_id'] in ids:
                result[rec['name']] = rec['res_id']
        return result

