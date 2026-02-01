from odoo import models, fields, api
from odoo.exceptions import UserError


class GenerateReconciliationInvoice(models.TransientModel):
    _name = 'surgery.generate.reconciliation.so'
    _description = 'Generate Reconciliation Invoice'

    payment_line_ids = fields.Many2many(
        'surgery.payment.line',
        string='Payment Lines'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Company',
        readonly=True
    )

    line_count = fields.Integer(
        string='Number of Lines',
        compute='_compute_summary'
    )

    gross_amount = fields.Monetary(
        string='Gross Amount',
        compute='_compute_summary',
        currency_field='currency_id',
        help='Total before commission/fees'
    )

    # Fee/commission - simple manual entry
    fee_amount = fields.Monetary(
        string='Commission',
        currency_field='currency_id',
        help='Commission amount to deduct (enter 0 for no fee)'
    )

    net_amount = fields.Monetary(
        string='Net Amount',
        compute='_compute_net',
        currency_field='currency_id',
        help='Amount after commission (what you receive)'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    @api.depends('payment_line_ids')
    def _compute_summary(self):
        for wizard in self:
            wizard.line_count = len(wizard.payment_line_ids)
            wizard.gross_amount = sum(wizard.payment_line_ids.mapped('expected_amount'))

    @api.depends('gross_amount', 'fee_amount')
    def _compute_net(self):
        for wizard in self:
            wizard.net_amount = wizard.gross_amount - (wizard.fee_amount or 0)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError("Please select payment lines to reconcile.")

        payment_lines = self.env['surgery.payment.line'].browse(active_ids)

        # Validate: only insurance or surgicenter lines
        invalid_lines = payment_lines.filtered(lambda l: l.payment_source == 'client')
        if invalid_lines:
            raise UserError("Cannot generate invoice for client payment lines. Select only insurance or surgicenter lines.")

        # Validate: all must have a company
        no_company = payment_lines.filtered(lambda l: not l.partner_id)
        if no_company:
            raise UserError("All selected lines must have a Company assigned.")

        # Validate: all must be from the same company
        companies = payment_lines.mapped('partner_id')
        if len(companies) > 1:
            company_names = ', '.join(companies.mapped('name'))
            raise UserError(
                f"All selected lines must be from the same company.\n"
                f"Found: {company_names}\n\n"
                "Please filter by company first and select lines from only one company."
            )

        # Validate: none already reconciled
        already_reconciled = payment_lines.filtered(lambda l: l.reconciliation_invoice_id)
        if already_reconciled:
            raise UserError(
                f"{len(already_reconciled)} line(s) already have a reconciliation invoice. "
                "Please deselect them or delete the existing invoice first."
            )

        res['payment_line_ids'] = [(6, 0, payment_lines.ids)]
        res['partner_id'] = companies[0].id if companies else False

        return res

    def action_generate_so(self):
        """Generate the Invoice for reconciliation and mark it as paid"""
        self.ensure_one()

        if not self.payment_line_ids:
            raise UserError("No payment lines selected.")

        # Build invoice lines - use expected_amount (gross)
        invoice_line_vals = []
        for payment_line in self.payment_line_ids:
            # Build description
            desc_parts = [f"Case {payment_line.surgery_case_id.name}"]
            if payment_line.reference:
                desc_parts.append(f"Claim #{payment_line.reference}")
            if payment_line.patient_id:
                desc_parts.append(f"Patient: {payment_line.patient_id.name}")

            invoice_line_vals.append((0, 0, {
                'name': " | ".join(desc_parts),
                'quantity': 1,
                'price_unit': payment_line.expected_amount,
            }))

        # Add commission/fee as negative line (discount)
        if self.fee_amount and self.fee_amount > 0:
            invoice_line_vals.append((0, 0, {
                'name': f"Commission - {self.partner_id.name}",
                'quantity': 1,
                'price_unit': -self.fee_amount,
            }))

        # Create Invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': 'Surgery Reconciliation',
            'invoice_line_ids': invoice_line_vals,
        }

        invoice = self.env['account.move'].create(invoice_vals)

        # Post the invoice
        invoice.action_post()

        # Link payment lines to invoice lines (skip the fee line)
        product_lines = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product' and l.price_unit >= 0
        )
        for payment_line, invoice_line in zip(self.payment_line_ids, product_lines):
            payment_line.reconciliation_invoice_line_id = invoice_line.id

        # Register payment to mark invoice as paid
        payment_register = self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=invoice.ids,
        ).create({
            'payment_date': fields.Date.context_today(self),
        })
        payment_register.action_create_payments()

        # Open the created Invoice
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reconciliation Invoice',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

