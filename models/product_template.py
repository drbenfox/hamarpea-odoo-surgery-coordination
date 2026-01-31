from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    service_tracking = fields.Selection(
        selection_add=[
            ('surgery_case', 'Surgery Case'),
        ],
        ondelete={'surgery_case': 'set default'}
    )

    is_informational = fields.Boolean(
        string='Informational Only',
        default=False,
        help='When added to a sales order, this product will appear on the quotation '
             'but will NOT be included in invoices. Use for reference items like '
             'surgical center fees that are billed separately.'
    )
