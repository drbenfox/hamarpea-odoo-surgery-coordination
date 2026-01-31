from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    service_tracking = fields.Selection(
        selection_add=[
            ('surgery_case', 'Surgery Case'),
        ],
        ondelete={'surgery_case': 'set default'}
    )
