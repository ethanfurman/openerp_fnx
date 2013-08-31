"enhancements to allow displaying and searching the external_id field"

from openerp import tools
from openerp.osv import osv, fields

class ir_model_data(osv.Model):
    "adds methods for retrieving and setting the external_id of records"
    _name = 'ir.model.data'
    _inherit = 'ir.model.data'

    @tools.ormcache()
    def _get_id_via_resid(self, cr, uid, model, res_id):
        """
        Returns id of the ir.model.data record corresponding to a given
        model and res_id (cached) or raise a ValueError if not found
        """
        ids = self.search(cr, uid, [('model','=',model), ('res_id','=', res_id)])
        if not ids:
            raise ValueError('No external ID currently defined in the system for: %s.%s' % (model, res_id))
        # the sql constraints ensure us we have only one result
        return ids[0]
        
    @tools.ormcache()
    def _get_model_records(self, cr, uid, model):
        """
        Returns the ids of the ir.model.data records corresponding to a
        given model or raise a ValueError if none found
        """
        context = {}
        ids = self.search(cr, uid, [('model', '=', model)])
        if not ids:
            return []
        return self.browse(cr, uid, ids)
        
    @tools.ormcache()
    def get_object_reference_from_model_resid(self, cr, uid, model, res_id):
        """
        Returns (xml_id, ) corresponding to a given model and res_id (cached)
        or raise ValueError if not found
        """
        data_id = self._get_id_via_resid(cr, uid, model, res_id)
        res = self.read(cr, uid, data_id, ['xml_id'])
        if not res['xml_id']:
            raise ValueError('No external ID currently defined in the system for: %s.%s' % (model, res_id))
        return (res['xml_id'], )

    def get_object_from_model_resid(self, cr, uid, model, res_id, context=None):
        """Returns a browsable record for the given model name and res_id or raise ValueError if not found"""
        id = self._get_id_via_resid(cr, uid, model, res_id)
        result = self.browse(cr, uid, id, context=context)
        if not result.exists():
            raise ValueError('No record found for %s.%s. It may have been deleted.' % (model, res_id))
        return result
ir_model_data()
