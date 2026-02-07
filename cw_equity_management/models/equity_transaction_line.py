# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EquityTransactionLine(models.Model):
    _name = 'equity.transaction.line'
    _description = 'Equity Transaction Line'
    _order = 'id'
    _rec_name = 'account_id'

    transaction_id = fields.Many2one(
        'equity.transaction',
        string='Equity Transaction',
        required=True,
        ondelete='cascade'
    )
    company_id = fields.Many2one(
        'res.company',
        related='transaction_id.company_id',
        string='Company',
        readonly=True,
        store=True
    )
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        required=True,
        domain="[('company_ids', 'in', company_id), ('account_type', 'in', ['asset_cash', 'asset_current', 'asset_fixed', 'asset_non_current', 'liability_current'])]"
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='transaction_id.currency_id',
        string='Currency',
        readonly=True
    )

    @api.constrains('amount')
    def _check_positive_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Line amount must be positive."))
