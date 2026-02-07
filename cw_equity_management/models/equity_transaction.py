# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EquityTransaction(models.Model):
    _name = 'equity.transaction'
    _description = 'Equity Transaction (Capital Contribution/Withdrawal)'
    _order = 'date desc, id desc'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True
    )
    # Transaction type
    transaction_type = fields.Selection([
        ('contribution', 'Capital Contribution'),
        ('withdrawal', 'Capital Withdrawal'),
        ('asset_contribution', 'Asset Contribution'),
    ], string='Transaction Type', required=True, default='contribution')
    
    # Partner involved in the transaction
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        domain=[('is_equity_owner', '=', True)],
        help='The equity owner involved in this transaction'
    )

    @api.onchange('transaction_type')
    def _onchange_transaction_type(self):
        """Make partner_id not required for asset contributions"""
        if self.transaction_type == 'asset_contribution':
            # For asset contributions, partner_id is not used directly
            # Splits are configured separately
            pass  # We'll handle this in constraints instead
    
    # Company where the transaction applies
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='The company where this transaction applies'
    )
    
    # Amount of the transaction
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
        readonly=True,
        currency_field='currency_id',
        help='The amount of the transaction'
    )
    
    # Date of the transaction
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        help='Date of the transaction'
    )
    
    # Reference for the transaction
    reference = fields.Char(
        string='Reference',
        help='Reference for this transaction'
    )
    
    # Description
    description = fields.Text(
        string='Description',
        help='Detailed description of the transaction'
    )
    
    # Related equity ownership record
    ownership_id = fields.Many2one(
        'equity.ownership',
        string='Equity Ownership',
        compute='_compute_ownership_id',
        store=True,
        help='Related equity ownership record'
    )
    
    # Generated journal entry
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        help='Generated journal entry for this transaction'
    )
    move_name = fields.Char(
        string='Journal Entry Number',
        related='move_id.name',
        readonly=True
    )
    
    # State of the transaction
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', readonly=True, copy=False)
    
    # Currency for monetary fields
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    # Account mapping for the transaction
    line_ids = fields.One2many(
        'equity.transaction.line',
        'transaction_id',
        string='Asset/Cash/Bank Lines'
    )

    # Split lines for asset contributions
    split_line_ids = fields.One2many(
        'equity.asset.contribution.split',
        'transaction_id',
        string='Asset Contribution Splits'
    )

    # Flag to indicate if splits are configured
    splits_configured = fields.Boolean(
        string='Splits Configured',
        compute='_compute_splits_configured',
        store=True
    )

    @api.depends('line_ids.amount')
    def _compute_amount(self):
        for record in self:
            record.amount = sum(record.line_ids.mapped('amount'))

    @api.depends('transaction_type', 'split_line_ids')
    def _compute_splits_configured(self):
        """Compute if splits are configured for asset contributions"""
        for record in self:
            if record.transaction_type == 'asset_contribution':
                record.splits_configured = bool(record.split_line_ids)
            else:
                record.splits_configured = True  # Not applicable for other types
    
    @api.depends('partner_id', 'transaction_type', 'amount', 'date', 'reference')
    def _compute_name(self):
        for record in self:
            if record.reference:
                record.name = record.reference
                continue
            if record.partner_id and record.amount and record.date:
                record.name = f"{record.transaction_type.title()} - {record.partner_id.name} - {record.amount}"
            else:
                record.name = _("Draft")

    @api.depends('partner_id', 'company_id', 'date')
    def _compute_ownership_id(self):
        """Compute the related equity ownership record"""
        for record in self:
            # Only compute ownership for transaction types that require it
            if record.transaction_type in ['contribution', 'withdrawal'] and record.partner_id:
                ownership = self.env['equity.ownership'].search([
                    ('partner_id', '=', record.partner_id.id),
                    ('company_id', '=', record.company_id.id),
                    ('date_from', '<=', record.date),
                    '|', ('date_to', '=', False), ('date_to', '>=', record.date)
                ], limit=1)
                record.ownership_id = ownership
            else:
                record.ownership_id = None
    
    @api.constrains('amount')
    def _check_positive_amount(self):
        """Ensure amount is positive"""
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_("Transaction amount must be positive."))
    
    @api.constrains('date')
    def _check_date_in_ownership_period(self):
        """Ensure transaction date is within ownership period"""
        for record in self:
            if record.ownership_id:
                if record.date < record.ownership_id.date_from:
                    raise ValidationError(_(
                        "Transaction date must be after the ownership start date (%s).") %
                        record.ownership_id.date_from)

                if (record.ownership_id.date_to and
                    record.date > record.ownership_id.date_to):
                    raise ValidationError(_(
                        "Transaction date must be before the ownership end date (%s).") %
                        record.ownership_id.date_to)
    
    @api.constrains('line_ids')
    def _check_lines_present(self):
        for record in self:
            if record.transaction_type in ['contribution', 'withdrawal'] and not record.line_ids:
                raise ValidationError(_("Please add at least one cash/bank line."))
            elif record.transaction_type == 'asset_contribution' and not record.line_ids:
                raise ValidationError(_("Please add at least one asset account line for asset contributions."))

    @api.constrains('partner_id', 'transaction_type')
    def _check_partner_required_for_transaction_types(self):
        """Ensure partner is required for certain transaction types"""
        for record in self:
            if record.transaction_type in ['contribution', 'withdrawal'] and not record.partner_id:
                raise ValidationError(_("Partner is required for this transaction type."))
    
    def action_post(self):
        """Post the transaction and create the journal entry"""
        for record in self:
            if record.state != 'draft':
                continue

            # Validate required fields
            if record.transaction_type in ['contribution', 'withdrawal'] and not record.line_ids:
                raise ValidationError(_("Please add at least one cash/bank line for this transaction."))
            elif record.transaction_type == 'asset_contribution':
                if not record.line_ids:
                    raise ValidationError(_("Please add at least one asset account line for asset contributions."))
                if not record.split_line_ids:
                    raise ValidationError(_("Please configure how to split the asset contribution among owners."))
                record._validate_splits()

            if record.transaction_type in ['contribution', 'withdrawal'] and not record.ownership_id:
                raise ValidationError(_("No active equity ownership found for this partner on the transaction date."))

            # Create the journal entry
            move_vals = record._prepare_journal_entry_vals()
            move = self.env['account.move'].create(move_vals)

            # Post the journal entry
            move.action_post()

            # Update transaction record
            record.write({
                'move_id': move.id,
                'state': 'posted'
            })

    def _validate_splits(self):
        """Validate that splits are properly configured for asset contributions"""
        self.ensure_one()

        if self.transaction_type != 'asset_contribution':
            return

        if not self.split_line_ids:
            raise ValidationError(_("Asset contributions must have at least one split allocation."))

        # Check for duplicate partners in split lines
        partner_ids = [split_line.partner_id.id for split_line in self.split_line_ids]
        if len(partner_ids) != len(set(partner_ids)):
            raise ValidationError(_("Each partner can only appear once in the split allocations."))

        # Calculate total based on split type
        total_split_amount = 0.0
        total_asset_value = sum(self.line_ids.mapped('amount'))

        for split_line in self.split_line_ids:
            if split_line.split_type == 'percentage':
                if split_line.percentage < 0 or split_line.percentage > 100:
                    raise ValidationError(_("Split percentage must be between 0 and 100%."))
                total_split_amount += total_asset_value * (split_line.percentage / 100.0)
            elif split_line.split_type == 'manual':
                if split_line.manual_amount < 0:
                    raise ValidationError(_("Manual split amount must be positive."))
                total_split_amount += split_line.manual_amount

        # Allow for small rounding differences
        if abs(total_split_amount - total_asset_value) > 0.01:
            raise ValidationError(_(
                "The total split allocation (%.2f) does not match the total asset value (%.2f). "
                "Please adjust the splits so they sum to the total asset value.") %
                (total_split_amount, total_asset_value))

    @api.constrains('transaction_type', 'split_line_ids')
    def _check_asset_contribution_splits(self):
        """Validate splits for asset contributions"""
        for record in self:
            if record.transaction_type == 'asset_contribution':
                record._validate_splits()
    
    def _prepare_journal_entry_vals(self):
        """Prepare journal entry values for the transaction"""
        self.ensure_one()

        # Prepare move lines
        move_lines = []
        total_amount = sum(self.line_ids.mapped('amount'))

        if self.transaction_type == 'contribution':
            # Get the shared equity account from company settings
            equity_account = self.company_id.equity_shared_account_id
            if not equity_account:
                raise ValidationError(_("Please configure the shared equity account for company %s") % self.company_id.name)

            # For contribution: debit each cash/bank line, credit shared equity account (total)
            for line in self.line_ids:
                move_lines.append({
                    'name': f'Capital Contribution from {self.partner_id.name}',
                    'account_id': line.account_id.id,
                    'debit': line.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                })
            move_lines.append({
                'name': f'Capital Contribution from {self.partner_id.name}',
                'account_id': equity_account.id,
                'debit': 0.0,
                'credit': total_amount,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
            })
        elif self.transaction_type == 'asset_contribution':
            # For asset contribution: debit each asset line, credit equity accounts based on splits
            for line in self.line_ids:
                move_lines.append({
                    'name': f'Asset Contribution - {line.account_id.name}',
                    'account_id': line.account_id.id,
                    'debit': line.amount,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                })

            # Credit equity accounts based on splits
            equity_account = self.company_id.equity_shared_account_id
            if not equity_account:
                raise ValidationError(_("Please configure the shared equity account for company %s") % self.company_id.name)

            for split_line in self.split_line_ids:
                move_lines.append({
                    'name': f'Asset Contribution from {split_line.partner_id.name}',
                    'account_id': equity_account.id,
                    'debit': 0.0,
                    'credit': split_line.calculated_amount,
                    'partner_id': split_line.partner_id.id,
                    'currency_id': self.currency_id.id,
                })
        else:  # withdrawal
            # For withdrawal: debit shared drawing account, credit cash
            drawing_account = self.company_id.drawing_shared_account_id
            if not drawing_account:
                raise ValidationError(_("Please configure the shared drawing account for company %s") % self.company_id.name)

            move_lines.append({
                'name': f'Capital Withdrawal to {self.partner_id.name}',
                'account_id': drawing_account.id,
                'debit': total_amount,
                'credit': 0.0,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
            })
            for line in self.line_ids:
                move_lines.append({
                    'name': f'Capital Withdrawal to {self.partner_id.name}',
                    'account_id': line.account_id.id,
                    'debit': 0.0,
                    'credit': line.amount,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                })

        # Create journal entry
        journal = self.env['account.journal'].search([
            ('type', 'in', ['general']),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        # Customize the reference based on transaction type
        if self.transaction_type == 'asset_contribution':
            ref_label = 'Capital Contribution'
            ref_detail = self.reference or 'Asset Contribution'
        else:
            ref_detail = self.reference or (self.partner_id.name if self.partner_id else self.transaction_type.title())
            ref_label = self.transaction_type.title()

        return {
            'ref': f'{ref_label} - {ref_detail}',
            'date': self.date,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'equity_transaction_id': self.id,  # Link back to the transaction
        }
    
    def action_cancel(self):
        """Cancel the transaction and reverse the journal entry"""
        for record in self:
            if record.state != 'posted':
                continue
                
            if record.move_id:
                # Reverse the journal entry
                reversal_wizard = self.env['account.move.reversal'].create({
                    'move_ids': [(4, record.move_id.id)],
                    'date': fields.Date.context_today(record),
                    'reason': f'Reversal of {record.transaction_type} transaction',
                })
                reversal_wizard.reverse_moves()
                
                # Update transaction record
                record.write({
                    'move_id': False,
                    'state': 'cancelled'
                })
    
    def action_draft(self):
        """Reset to draft state"""
        for record in self:
            if record.state == 'cancelled':
                record.state = 'draft'
    
    def name_get(self):
        """Use the computed name for display"""
        return super().name_get()

    def action_view_journal_entry(self):
        """Action to view the generated journal entry"""
        self.ensure_one()
        if self.move_id:
            return {
                'name': _('Journal Entry'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': self.move_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window.close'}

    @api.model
    def get_dashboard_data(self, dummy_records, date_from=None, date_to=None, partner_id=None, transaction_type=None, company_id=None):
        """
        Method to get dashboard data directly for the JavaScript dashboard
        The first parameter is the recordset (even if empty for @api.model methods)
        """
        # Get the report model
        report_model = self.env['report.cw_equity_management.equity_transaction_report']

        data = {
            'date_from': date_from,
            'date_to': date_to,
            'partner_id': partner_id,
            'transaction_type': transaction_type,
            'company_id': company_id or self.env.company.id,
        }

        report_values = report_model._get_report_values(None, data=data)

        return {
            'transactions': report_values.get('transactions', []),
            'equity_info': report_values.get('equity_info', []),
            'date_from': report_values.get('date_from'),
            'date_to': report_values.get('date_to'),
            'partner_id': report_values.get('partner_id'),
            'transaction_type': report_values.get('transaction_type'),
            'company': {
                'name': report_values.get('company', {}).name if report_values.get('company') else '',
            }
        }
