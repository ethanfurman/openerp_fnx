"various OpenERP routines related to exposing fis ids stored in xml_id in ir.model.data"

from openerp.exceptions import ERPError
import logging

_logger = logging.getLogger(__name__)

class xmlid(object):

    def create(self, cr, uid, values, context=None):
        xml_id = values.get('xml_id')
        module = values.get('module')
        if sum(1 for k in (xml_id, module) if k) == 1:
            raise ERPError('Error', 'if one of (xml_id, module) is set, both must be (%r, %r)' % (xml_id, module))
        new_id = super(xmlid, self).create(cr, uid, values, context=context)
        if xml_id and module:
            imd = self.pool.get('ir.model.data')
            # check for orphaned xml_ids
            orphan = imd.search(cr, uid, [('name','=',xml_id),('module','=',module),('model','=',self._name)], context=context)
            if orphan:
                # this shouldn't happen - log a warning
                _logger.warning('FIS ID orphan found: <%s::%s>', module, xml_id)
                # actually an orphan?
                found = imd.browse(cr, uid, orphan[0], context=context)
                record = self.browse(cr, uid, found.res_id, context=context)
                if record:
                    # not an orphan, and duplicates not allowed!
                    _logger.warning('orphan id: %r' % (record.id, ))
                    raise ERPError('Error', '%s:%s belongs to %s' % (module, xml_id, record.id))
                else:
                    # adopt the orphan
                    imd.write(cr, uid, orphan[0], {'res_id':new_id}, context=context)
            else:
                imd.create(cr, uid, {'module':module, 'name':xml_id, 'model':self._name, 'res_id':new_id}, context=context)
        return new_id

    def name_search(self, cr, uid, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if name:
            if name[0] == ' ':
                ids = self.search(cr, uid, [('xml_id','ilike',name.lstrip())]+ args, limit=limit, context=context)
            else:
                ids = self.search(cr, uid, [('xml_id','=ilike',name+'%')]+ args, limit=limit, context=context)
            if ids:
                return self.name_get(cr, uid, ids, context=context)
        return super(xmlid, self).name_search(cr, uid, name=name, args=args, operator=operator, context=context, limit=limit)

    def write(self, cr, uid, ids, values, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        xml_id = values.get('xml_id')
        module = values.get('module')
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
        return True

    def get_xml_id_map(self, cr, uid, module, ids=None, context=None):
        "return {xml_id: id} for all xml_ids in module"
        imd = self.pool.get('ir.model.data')
        result = {}
        for rec in imd.read(cr, uid, [('model','=',self._name),('module','=',module)], fields=['name','res_id'], context=context):
            if ids is None or rec['res_id'] in ids:
                result[rec['name']] = rec['res_id']
        return result

