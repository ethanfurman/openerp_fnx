"enhancements to allow displaying and searching the external_id field"

from openerp.osv import osv

class ir_model_data(osv.Model):
    "adds methods for retrieving and setting the external_id of records"
    _name = 'ir.model.data'
    _inherit = 'ir.model.data'

    def get_ids_from_model_resid(self, cr, uid, module, model, res_ids):
        """
        Returns ids corresponding to a given model and res_id
        or raise ValueError if none found
        """
        imd_ids = self.search(cr, uid, [('model','=',model), ('res_id','in', res_ids)])
        if not ids:
            raise ValueError('No external ID currently defined in the system for: %s.%s.%s' % (module, model, res_id))
        ids = [
                r.res_id
                for r in self.read(cr, uid, imd_ids)
                ]
        return ids
