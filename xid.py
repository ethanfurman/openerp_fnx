"various OpenERP routines related to exposing fis ids stored in xml_id in ir.model.data"

from osv.osv import except_osv as ERPError
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
                _logger.warning('FIS ID orphan found: %s::%s', xml_id, module)
                # actually an orphan?
                found = imd.browse(cr, uid, orphan[0], context=context)
                record = self.browse(cr, uid, found.res_id, context=context)
                if record:
                    # not an orphan, and duplicates not allowed!
                    raise ERPError('Error', '%s:%s belongs to %s' % (module, xml_id, record.name))
                else:
                    # adopt the orphan
                    imd.write(cr, uid, orphan[0], {'res_id':new_id}, context=context)
            else:
                imd.create(cr, uid, {'module':module, 'name':xml_id, 'model':self._name, 'res_id':new_id}, context=context)
        return new_id

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
        for rec in imd.browse(cr, uid, [('model','=',self._name),('module','=',module)], context=context):
            if ids is None or rec.res_id in ids:
                result[rec.name] = rec.res_id
        return result

