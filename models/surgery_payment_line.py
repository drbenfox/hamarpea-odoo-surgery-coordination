from odoo import models, fields, api


class SurgeryPaymentLine(models.Model):
    _name = 'surgery.payment.line'
    _description = 'Surgery Payment Line'
    _order = 'payment_source, id'

    surgery_case_id = fields.Many2one(
        'surgery.case',
        string='Surgery Case',
        required=True,
        ondelete='cascade'
    )

    payment_source = fields.Selection([
        ('client', 'Client'),
        ('insurance', 'Insurance'),
        ('surgicenter', 'Surgicenter')
    ], required=True, string='Source')

    partner_id = fields.Many2one(
        'res.partner',
        string='Company',
        help='Insurance company or surgical center'
    )

    expected_amount = fields.Monetary(
        string='Expected',
        currency_field='currency_id'
    )

    received_amount = fields.Monetary(
        string='Received',
        currency_field='currency_id'
    )

    balance = fields.Monetary(
        string='Balance',
        compute='_compute_balance',
        store=True,
        currency_field='currency_id'
    )

    # Payment status (for all lines) - editable with auto-suggestion
    status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
        ('paid', 'Paid')
    ], default='unpaid', string='Payment Status')

    # Claim status (for insurance lines only)
    claim_status = fields.Selection([
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('denied', 'Denied')
    ], string='Claim Status', default='pending')

    reference = fields.Char(
        string='Reference',
        help='Claim number, invoice reference, etc.'
    )

    payment_date = fields.Date(
        string='Payment Date'
    )

    currency_id = fields.Many2one(
        related='surgery_case_id.currency_id',
        store=True
    )

    # For client payments - link to the actual payment
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice'
    )

    payment_id = fields.Many2one(
        'account.payment',
        string='Payment'
    )

    # Related fields for Indirect Payments view
    patient_id = fields.Many2one(
        related='surgery_case_id.partner_id',
        string='Patient',
        store=True
    )

    sale_order_id = fields.Many2one(
        related='surgery_case_id.sale_order_id',
        string='Sale Order',
        store=True
    )

    sale_order_balance = fields.Monetary(
        compute='_compute_sale_order_balance',
        string='SO Balance',
        currency_field='currency_id'
    )

    # For reconciliation - link to generated invoice for insurance/surgicenter
    reconciliation_invoice_line_id = fields.Many2one(
        'account.move.line',
        string='Reconciliation Invoice Line',
        help='The invoice line generated when reconciling this payment'
    )

    reconciliation_invoice_id = fields.Many2one(
        related='reconciliation_invoice_line_id.move_id',
        string='Reconciliation Invoice',
        store=True
    )

    @api.onchange('payment_source')
    def _onchange_payment_source(self):
        """Clear partner and return appropriate domain when source changes"""
        self.partner_id = False
        if self.payment_source == 'insurance':
            return {'domain': {'partner_id': [('account_type', 'in', ['private_insurance', 'kupat_holim'])]}}
        elif self.payment_source == 'surgicenter':
            return {'domain': {'partner_id': [('account_type', '=', 'operating_room')]}}
        return {'domain': {'partner_id': []}}

    @api.depends('expected_amount', 'received_amount')
    def _compute_balance(self):
        for line in self:
            line.balance = (line.expected_amount or 0) - (line.received_amount or 0)

    @api.onchange('expected_amount', 'received_amount')
    def _onchange_amounts(self):
        """Auto-suggest payment status based on amounts"""
        balance = (self.expected_amount or 0) - (self.received_amount or 0)
        if balance <= 0 and self.expected_amount > 0:
            self.status = 'paid'
        elif self.received_amount > 0:
            self.status = 'partial'
        else:
            self.status = 'unpaid'

    @api.depends('surgery_case_id.sale_order_total', 'surgery_case_id.payment_total_received')
    def _compute_sale_order_balance(self):
        for line in self:
            case = line.surgery_case_id
            line.sale_order_balance = (case.sale_order_total or 0) - (case.payment_total_received or 0)

    # ==================== CHATTER TRACKING ====================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.surgery_case_id and record.payment_source != 'client':
                source_label = dict(self._fields['payment_source'].selection).get(record.payment_source, record.payment_source)
                msg = f"Payment line added: {source_label}"
                if record.partner_id:
                    msg += f" - {record.partner_id.name}"
                if record.expected_amount:
                    msg += f" ({record.currency_id.symbol}{record.expected_amount:,.2f})"
                record.surgery_case_id.message_post(body=msg)
        return records

    def write(self, vals):
        # Track significant changes
        tracked_fields = {'expected_amount', 'received_amount', 'status', 'claim_status', 'reconciliation_invoice_line_id'}
        if tracked_fields & set(vals.keys()):
            for record in self:
                changes = []

                if 'expected_amount' in vals and vals['expected_amount'] != record.expected_amount:
                    changes.append(f"expected: {record.currency_id.symbol}{record.expected_amount or 0:,.2f} → {record.currency_id.symbol}{vals['expected_amount']:,.2f}")

                if 'received_amount' in vals and vals['received_amount'] != record.received_amount:
                    changes.append(f"received: {record.currency_id.symbol}{record.received_amount or 0:,.2f} → {record.currency_id.symbol}{vals['received_amount']:,.2f}")

                if 'status' in vals and vals['status'] != record.status:
                    old_label = dict(self._fields['status'].selection).get(record.status, record.status)
                    new_label = dict(self._fields['status'].selection).get(vals['status'], vals['status'])
                    changes.append(f"status: {old_label} → {new_label}")

                if 'claim_status' in vals and vals['claim_status'] != record.claim_status:
                    old_label = dict(self._fields['claim_status'].selection).get(record.claim_status, record.claim_status)
                    new_label = dict(self._fields['claim_status'].selection).get(vals['claim_status'], vals['claim_status'])
                    changes.append(f"claim: {old_label} → {new_label}")

                if 'reconciliation_invoice_line_id' in vals and vals['reconciliation_invoice_line_id']:
                    invoice_line = self.env['account.move.line'].browse(vals['reconciliation_invoice_line_id'])
                    if invoice_line.move_id:
                        changes.append(f"linked to reconciliation invoice {invoice_line.move_id.name}")

                if changes and record.surgery_case_id:
                    source_label = dict(self._fields['payment_source'].selection).get(record.payment_source, record.payment_source)
                    company = record.partner_id.name if record.partner_id else ''
                    msg = f"Payment line updated ({source_label}{' - ' + company if company else ''}): {', '.join(changes)}"
                    record.surgery_case_id.message_post(body=msg)

        return super().write(vals)
