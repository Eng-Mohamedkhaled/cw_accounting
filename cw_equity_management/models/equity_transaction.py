# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EquityTransaction(models.Model):
    _name = 'equity.transaction'
    _description = 'Equity Transaction (Capital Contribution/Withdrawal)'
    _order = 'date desc, id desc'
    
    # Transaction type
    transaction_type = fields.Selection([
        ('contribution', 'Capital Contribution'),
        ('withdrawal', 'Capital Withdrawal'),
    ], string='Transaction Type', required=True, default='contribution')
    
    # Partner involved in the transaction
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        domain=[('is_equity_owner', '=', True)],
        help='The equity owner involved in this transaction'
    )
    
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
        required=True,
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
    cash_account_id = fields.Many2one(
        'account.account',
        string='Cash/Bank Account',
        domain="[('company_ids', 'in', company_id), ('account_type', 'in', ['asset_cash', 'asset_current', 'liability_current'])]",
        help='Account where cash is received from (for contributions) or paid to (for withdrawals)'
    )
    
    @api.depends('partner_id', 'company_id', 'date')
    def _compute_ownership_id(self):
        """Compute the related equity ownership record"""
        for record in self:
            ownership = self.env['equity.ownership'].search([
                ('partner_id', '=', record.partner_id.id),
                ('company_id', '=', record.company_id.id),
                ('date_from', '<=', record.date),
                '|', ('date_to', '=', False), ('date_to', '>=', record.date)
            ], limit=1)
            record.ownership_id = ownership
    
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
    
    @api.constrains('cash_account_id', 'company_id')
    def _check_cash_account_company(self):
        """Ensure cash account belongs to the same company"""
        for record in self:
            if (record.cash_account_id and
                record.company_id not in record.cash_account_id.company_ids):
                raise ValidationError(_(
                    "The cash account must belong to the same company as the transaction."
                ))
    
    def action_post(self):
        """Post the transaction and create the journal entry"""
        for record in self:
            if record.state != 'draft':
                continue
                
            # Validate required fields
            if not record.cash_account_id:
                raise ValidationError(_("Please specify a cash/bank account for this transaction."))
            
            if not record.ownership_id:
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
    
    def _prepare_journal_entry_vals(self):
        """Prepare journal entry values for the transaction"""
        self.ensure_one()

        # Get the shared equity account from company settings
        equity_account = self.company_id.equity_shared_account_id
        if not equity_account:
            raise ValidationError(_("Please configure the shared equity account for company %s") % self.company_id.name)

        cash_account = self.cash_account_id

        # Prepare move lines
        move_lines = []

        if self.transaction_type == 'contribution':
            # For contribution: debit cash, credit shared equity account
            move_lines.extend([
                {
                    'name': f'Capital Contribution from {self.partner_id.name}',
                    'account_id': cash_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                },
                {
                    'name': f'Capital Contribution from {self.partner_id.name}',
                    'account_id': equity_account.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                }
            ])
        else:  # withdrawal
            # For withdrawal: debit shared drawing account, credit cash
            drawing_account = self.company_id.drawing_shared_account_id
            if not drawing_account:
                raise ValidationError(_("Please configure the shared drawing account for company %s") % self.company_id.name)

            move_lines.extend([
                {
                    'name': f'Capital Withdrawal to {self.partner_id.name}',
                    'account_id': drawing_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                },
                {
                    'name': f'Capital Withdrawal to {self.partner_id.name}',
                    'account_id': cash_account.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                }
            ])

        # Create journal entry
        journal = self.env['account.journal'].search([
            ('type', 'in', ['general']),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        return {
            'ref': f'{self.transaction_type.title()} - {self.partner_id.name}',
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
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.transaction_type.title()} - {record.partner_id.name} - {record.amount}"
            result.append((record.id, name))
        return result

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