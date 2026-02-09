# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EquityDrawingClose(models.Model):
    _name = 'equity.drawing.close'
    _description = 'Equity Drawing Close Transaction'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        domain=[('is_equity_owner', '=', True)],
        required=True,
        help='The equity owner whose drawing account will be closed'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='The company where this drawing close applies'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        help='Date of the drawing close transaction'
    )
    
    reference = fields.Char(
        string='Reference',
        help='Reference for this drawing close transaction'
    )
    
    drawing_balance = fields.Monetary(
        string='Drawing Balance',
        compute='_compute_drawing_balance',
        store=True,
        currency_field='currency_id',
        help='Current drawing account balance for this partner'
    )
    
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
        help='Amount to close (absolute value of drawing balance)'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        help='Generated journal entry for this drawing close'
    )
    
    move_name = fields.Char(
        string='Journal Entry Number',
        related='move_id.name',
        readonly=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', readonly=True, copy=False)

    @api.depends('partner_id', 'company_id', 'date')
    def _compute_drawing_balance(self):
        """Calculate the current drawing account balance for the partner"""
        for record in self:
            if not record.partner_id or not record.company_id:
                record.drawing_balance = 0.0
                continue
            
            drawing_account = record.company_id.drawing_shared_account_id
            if not drawing_account:
                record.drawing_balance = 0.0
                continue
            
            # Query account move lines for this partner in the drawing account
            self.env.cr.execute("""
                SELECT SUM(aml.balance)
                FROM account_move_line aml
                JOIN account_move am ON aml.move_id = am.id
                WHERE aml.partner_id = %s
                  AND aml.account_id = %s
                  AND aml.date <= %s
                  AND aml.company_id = %s
                  AND am.state = 'posted'
            """, (record.partner_id.id, drawing_account.id, record.date, record.company_id.id))

            result = self.env.cr.fetchone()[0]
            drawing_balance = result or 0.0
            
            record.drawing_balance = drawing_balance

    @api.depends('drawing_balance')
    def _compute_amount(self):
        """Amount to close is the absolute value of the drawing balance"""
        for record in self:
            record.amount = abs(record.drawing_balance)

    @api.depends('partner_id', 'date', 'reference')
    def _compute_name(self):
        """Compute the name for the drawing close transaction"""
        for record in self:
            if record.reference:
                record.name = record.reference
            elif record.partner_id and record.date:
                record.name = f"Drawing Close - {record.partner_id.name} - {record.date}"
            else:
                record.name = _("Draft Drawing Close")

    def action_post(self):
        """Post the drawing close transaction"""
        for record in self:
            if record.state != 'draft':
                continue

            if record.amount <= 0:
                raise ValidationError(_("Cannot close drawing with zero or negative balance."))

            # Create the journal entry
            move_vals = record._prepare_journal_entry_vals()
            move = self.env['account.move'].create(move_vals)

            # Post the journal entry
            move.action_post()

            # Update drawing close record
            record.write({
                'move_id': move.id,
                'state': 'posted'
            })

    def _prepare_journal_entry_vals(self):
        """Prepare journal entry values for the drawing close"""
        self.ensure_one()

        # Ensure the required equity accounts exist
        self.company_id._ensure_equity_accounts_exist()

        # Get the drawing and equity accounts
        drawing_account = self.company_id.drawing_shared_account_id
        equity_account = self.company_id.equity_shared_account_id

        if not drawing_account:
            raise ValidationError(_("Please configure the shared drawing account for company %s") % self.company_id.name)
        if not equity_account:
            raise ValidationError(_("Please configure the shared equity account for company %s") % self.company_id.name)

        # Prepare move lines
        move_lines = []

        # Zero out the drawing account by doing the opposite of its current balance
        # In Odoo, balance = debit - credit
        # For drawing accounts, typically credits represent withdrawals (negative balance)
        # So to zero out the account, we do the opposite of the current balance
        if self.drawing_balance > 0:
            # Drawing account has a net debit balance (more debits than credits)
            # To zero it out, we credit the same amount
            move_lines.append({
                'name': f'Drawing Close for {self.partner_id.name}',
                'account_id': drawing_account.id,
                'debit': 0.0,
                'credit': self.amount,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
            })
            # Debit the equity account to compensate
            move_lines.append({
                'name': f'Drawing Close for {self.partner_id.name}',
                'account_id': equity_account.id,
                'debit': self.amount,
                'credit': 0.0,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
            })
        elif self.drawing_balance < 0:
            # Drawing account has a net credit balance (more credits than debits)
            # To zero it out, we debit the same amount
            move_lines.append({
                'name': f'Drawing Close for {self.partner_id.name}',
                'account_id': drawing_account.id,
                'debit': self.amount,
                'credit': 0.0,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
            })
            # Credit the equity account to compensate
            move_lines.append({
                'name': f'Drawing Close for {self.partner_id.name}',
                'account_id': equity_account.id,
                'debit': 0.0,
                'credit': self.amount,
                'partner_id': self.partner_id.id,
                'currency_id': self.currency_id.id,
            })

        # Create journal entry
        journal = self.env['account.journal'].search([
            ('type', 'in', ['general']),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        return {
            'ref': f'Drawing Close - {self.partner_id.name}',
            'date': self.date,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'drawing_close_id': self.id,  # Link back to the drawing close record
        }

    def action_cancel(self):
        """Cancel the drawing close transaction"""
        for record in self:
            if record.state != 'posted':
                continue

            if record.move_id:
                # Use the same journal as the original move for the reversal
                original_journal = record.move_id.journal_id

                # Reverse the journal entry
                reversal_wizard = self.env['account.move.reversal'].create({
                    'move_ids': [(4, record.move_id.id)],
                    'date': fields.Date.context_today(record),
                    'reason': 'Cancellation of Drawing Close',
                    'journal_id': original_journal.id,
                })
                reversal_wizard.reverse_moves()

            record.write({
                'move_id': False,
                'state': 'cancelled'
            })

    def action_draft(self):
        """Reset to draft state"""
        for record in self:
            if record.state == 'cancelled':
                record.state = 'draft'

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