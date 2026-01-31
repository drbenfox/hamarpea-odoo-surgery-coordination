from odoo import models, fields, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_informational = fields.Boolean(
        string='Informational Only',
        help='This line appears on quotation for customer reference but will not be invoiced',
        copy=False
    )

    surgery_case_id = fields.Many2one(
        'surgery.case',
        string='Surgery Case',
        copy=False,
        help='Surgery case created from this sales order line'
    )

    @api.depends('is_informational', 'product_uom_qty', 'qty_delivered', 'qty_invoiced')
    def _compute_qty_to_invoice(self):
        """Prevent informational lines from appearing as 'to invoice'"""
        super()._compute_qty_to_invoice()
        for line in self:
            if line.is_informational:
                line.qty_to_invoice = 0.0
                line.qty_invoiced = line.product_uom_qty

    def _prepare_invoice_line(self, **optional_values):
        """Skip informational lines when creating invoices"""
        if self.is_informational:
            return False
        return super()._prepare_invoice_line(**optional_values)

    def _surgery_case_generation(self):
        """Create surgery cases for lines with surgery_case service tracking"""
        SurgeryCase = self.env['surgery.case']

        for line in self:
            if line.product_id.service_tracking != 'surgery_case':
                continue
            if line.surgery_case_id:
                # Already has a surgery case linked
                continue

            # Get default surgeon from employee linked to current user or first available
            default_surgeon = self.env['hr.employee'].search([
                ('user_id', '=', self.env.user.id)
            ], limit=1)
            if not default_surgeon:
                default_surgeon = self.env['hr.employee'].search([], limit=1)

            # Create the surgery case
            surgery_case = SurgeryCase.create({
                'partner_id': line.order_id.partner_id.id,
                'surgery_product_id': line.product_id.id,
                'sale_order_id': line.order_id.id,
                'surgeon_employee_id': default_surgeon.id if default_surgeon else False,
                'surgery_plan': line.name,
            })

            # Link the surgery case back to the line
            line.surgery_case_id = surgery_case.id

            # Post a message on the surgery case
            surgery_case.message_post(
                body=f"Surgery case created from Sales Order {line.order_id.name}"
            )
