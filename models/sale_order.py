from odoo import models, fields


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    surgery_case_count = fields.Integer(
        compute='_compute_surgery_case_count',
        string='Surgery Cases'
    )

    def _compute_surgery_case_count(self):
        for order in self:
            order.surgery_case_count = self.env['surgery.case'].search_count([
                ('sale_order_id', '=', order.id)
            ])

    def _action_confirm(self):
        """On SO confirmation, create surgery cases for products with surgery_case tracking"""
        result = super()._action_confirm()

        # Generate surgery cases for relevant lines
        for order in self:
            order.order_line.sudo()._surgery_case_generation()

        return result

    def action_view_surgery_cases(self):
        """Smart button action to view linked surgery cases"""
        self.ensure_one()
        surgery_cases = self.env['surgery.case'].search([
            ('sale_order_id', '=', self.id)
        ])

        action = {
            'type': 'ir.actions.act_window',
            'name': 'Surgery Cases',
            'res_model': 'surgery.case',
            'view_mode': 'tree,form,kanban',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }

        if len(surgery_cases) == 1:
            action['view_mode'] = 'form'
            action['res_id'] = surgery_cases.id

        return action
