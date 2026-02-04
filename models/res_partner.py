from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Surgical Center fields (account_type = 'operating_room' defined in hamarpea-odoo-contacts)
    processing_fee_pct = fields.Float(
        string='Processing Fee %',
        help='Percentage deducted from surgeon fees (e.g., 4.0 for 4%)',
        digits=(5, 2)
    )
