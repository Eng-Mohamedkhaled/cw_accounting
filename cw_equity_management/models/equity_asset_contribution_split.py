# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EquityAssetContributionSplit(models.Model):
    """
    Model to handle splitting of asset contributions among multiple equity owners
    """
    _name = 'equity.asset.contribution.split'
    _description = 'Equity Asset Contribution Split'
    _order = 'sequence, id'

    transaction_id = fields.Many2one(
        'equity.transaction',
        string='Equity Transaction',
        required=True,
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        domain=[('is_equity_owner', '=', True)],
        help='The equity owner receiving this portion of the contribution'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of the split allocation'
    )

    split_type = fields.Selection([
        ('percentage', 'By Percentage'),
        ('manual', 'Manual Amount'),
    ], string='Split Type', required=True, default='manual')

    percentage = fields.Float(
        string='Percentage',
        digits=(16, 4),
        compute='_compute_percentage_from_ownership',
        inverse='_inverse_percentage',
        help='Percentage of the total asset value allocated to this partner'
    )

    manual_amount = fields.Monetary(
        string='Manual Amount',
        currency_field='currency_id',
        help='Fixed amount allocated to this partner'
    )

    calculated_amount = fields.Monetary(
        string='Calculated Amount',
        currency_field='currency_id',
        compute='_compute_calculated_amount',
        store=True,
        help='Amount that will be allocated to this partner'
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='transaction_id.currency_id',
        string='Currency',
        readonly=True
    )

    @api.depends('split_type', 'percentage', 'manual_amount', 'transaction_id.line_ids.amount')
    def _compute_calculated_amount(self):
        """Calculate the actual amount based on split type"""
        for record in self:
            if record.transaction_id:
                total_asset_value = sum(record.transaction_id.line_ids.mapped('amount'))
                
                if record.split_type == 'percentage':
                    record.calculated_amount = total_asset_value * (record.percentage / 100.0)
                elif record.split_type == 'manual':
                    record.calculated_amount = record.manual_amount
                else:
                    record.calculated_amount = 0.0
            else:
                record.calculated_amount = 0.0

    @api.constrains('percentage')
    def _check_percentage_range(self):
        """Ensure percentage is between 0 and 100"""
        for record in self:
            if record.split_type == 'percentage' and (record.percentage < 0 or record.percentage > 100):
                raise ValidationError(_("Split percentage must be between 0 and 100%."))

    @api.constrains('manual_amount')
    def _check_manual_amount_positive(self):
        """Ensure manual amount is positive"""
        for record in self:
            if record.split_type == 'manual' and record.manual_amount < 0:
                raise ValidationError(_("Manual split amount must be positive."))

    @api.depends('partner_id', 'transaction_id.date', 'transaction_id.company_id')
    def _compute_percentage_from_ownership(self):
        """Compute percentage based on equity ownership"""
        for record in self:
            if record.split_type == 'percentage' and record.partner_id:
                # Find the equity ownership for this partner in the transaction's company
                ownership = self.env['equity.ownership'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('company_id', '=', record.transaction_id.company_id.id),
                    ('date_from', '<=', record.transaction_id.date or fields.Date.context_today(record)),
                    '|', ('date_to', '=', False), ('date_to', '>=', record.transaction_id.date or fields.Date.context_today(record))
                ], limit=1)

                record.percentage = ownership.percentage if ownership else 0.0
            else:
                record.percentage = 0.0

    def _inverse_percentage(self):
        """Inverse method to allow manual override of percentage"""
        for record in self:
            # Allow manual override when needed
            pass

    @api.onchange('partner_id')
    def _onchange_partner_id_set_percentage(self):
        """Set percentage based on equity ownership when partner is selected"""
        if self.partner_id and self.split_type == 'percentage':
            # Find the equity ownership for this partner in the transaction's company
            ownership = self.env['equity.ownership'].search([
                ('partner_id', '=', self.partner_id.id),
                ('company_id', '=', self.transaction_id.company_id.id),
                ('date_from', '<=', self.transaction_id.date or fields.Date.context_today(self)),
                '|', ('date_to', '=', False), ('date_to', '>=', self.transaction_id.date or fields.Date.context_today(self))
            ], limit=1)

            if ownership:
                self.percentage = ownership.percentage

    @api.onchange('split_type')
    def _onchange_split_type_set_percentage(self):
        """Set percentage based on equity ownership when split type is changed to percentage"""
        if self.split_type == 'percentage' and self.partner_id:
            # Find the equity ownership for this partner in the transaction's company
            ownership = self.env['equity.ownership'].search([
                ('partner_id', '=', self.partner_id.id),
                ('company_id', '=', self.transaction_id.company_id.id),
                ('date_from', '<=', self.transaction_id.date or fields.Date.context_today(self)),
                '|', ('date_to', '=', False), ('date_to', '>=', self.transaction_id.date or fields.Date.context_today(self))
            ], limit=1)

            if ownership:
                self.percentage = ownership.percentage
            else:
                self.percentage = 0.0

    @api.constrains('split_type', 'percentage', 'manual_amount')
    def _check_split_values(self):
        """Ensure proper values based on split type"""
        for record in self:
            if record.split_type == 'percentage' and record.percentage is False:
                raise ValidationError(_("Percentage value is required when using percentage split type."))
            if record.split_type == 'manual' and record.manual_amount is False:
                raise ValidationError(_("Manual amount is required when using manual split type."))