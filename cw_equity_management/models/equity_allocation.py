# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class EquityAllocation(models.Model):
    _name = 'equity.allocation'
    _description = 'Profit & Loss Allocation to Equity Owners'
    _order = 'allocation_date desc, id desc'
    
    # Name of the allocation
    name = fields.Char(
        string='Name',
        required=True,
        default=lambda self: _('New Allocation'),
        help='Name of this allocation'
    )
    
    # Company for the allocation
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company for which profit/loss is allocated'
    )
    
    # Period for the allocation
    allocation_date = fields.Date(
        string='Allocation Date',
        required=True,
        default=fields.Date.context_today,
        help='Date of the allocation'
    )
    
    # Period for which profit/loss is calculated
    period_start = fields.Date(
        string='Period Start',
        required=True,
        help='Start date of the period for profit/loss calculation'
    )
    
    period_end = fields.Date(
        string='Period End',
        required=True,
        help='End date of the period for profit/loss calculation'
    )
    
    # Net profit/loss amount for the period
    net_amount = fields.Monetary(
        string='Net Profit/Loss',
        currency_field='currency_id',
        readonly=True,
        help='Calculated net profit or loss for the period'
    )
    
    # Status of the allocation
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
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
    
    # Reference to the journal entry created for this allocation
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        help='Generated journal entry for this allocation'
    )
    
    # Allocation lines showing how profit/loss is distributed
    allocation_line_ids = fields.One2many(
        'equity.allocation.line',
        'allocation_id',
        string='Allocation Lines',
        readonly=True
    )
    
    # Retained earnings account
    retained_earnings_account_id = fields.Many2one(
        'account.account',
        string='Retained Earnings Account',
        domain="[('company_ids', 'in', company_id), ('account_type', '=', 'equity_unaffected')]",
        help='Account for retained earnings'
    )
    
    @api.constrains('period_start', 'period_end', 'allocation_date')
    def _check_dates(self):
        """Validate that dates are in correct order"""
        for record in self:
            if record.period_start > record.period_end:
                raise ValidationError(_("Period start date must be before period end date."))
            
            if record.allocation_date < record.period_end:
                raise ValidationError(_("Allocation date cannot be before the period end date."))
    
    @api.onchange('company_id', 'period_start', 'period_end')
    def _onchange_calculate_net_amount(self):
        """Calculate net profit/loss when dates change"""
        if self.period_start and self.period_end and self.company_id:
            self.net_amount = self._calculate_net_profit_loss()
    
    def _calculate_net_profit_loss(self):
        """Calculate net profit/loss for the period"""
        # This is a simplified calculation - in practice, you'd use Odoo's reporting engine
        # or connect to the P&L report
        
        # Get income and expense accounts for the company
        income_accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('account_type', 'in', ['income', 'income_other'])
        ])
        
        expense_accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('account_type', 'in', ['expense', 'expense_direct_cost'])
        ])
        
        # Calculate total income
        income_query = """
            SELECT SUM(balance) FROM account_move_line 
            WHERE account_id IN %s 
            AND date >= %s 
            AND date <= %s 
            AND company_id = %s
            AND parent_state = 'posted'
        """
        
        expense_query = """
            SELECT SUM(balance) FROM account_move_line 
            WHERE account_id IN %s 
            AND date >= %s 
            AND date <= %s 
            AND company_id = %s
            AND parent_state = 'posted'
        """
        
        income_total = 0.0
        if income_accounts:
            self.env.cr.execute(income_query, (
                tuple(income_accounts.ids), 
                self.period_start, 
                self.period_end, 
                self.company_id.id
            ))
            income_result = self.env.cr.fetchone()[0]
            income_total = income_result or 0.0
        
        expense_total = 0.0
        if expense_accounts:
            self.env.cr.execute(expense_query, (
                tuple(expense_accounts.ids), 
                self.period_start, 
                self.period_end, 
                self.company_id.id
            ))
            expense_result = self.env.cr.fetchone()[0]
            expense_total = expense_result or 0.0
        
        # Net profit/loss = Income - Expenses
        net_amount = income_total - expense_total
        return net_amount
    
    def action_calculate(self):
        """Calculate profit/loss allocation"""
        for record in self:
            if record.state != 'draft':
                continue
            
            # Calculate net amount
            record.net_amount = record._calculate_net_profit_loss()
            
            # Create allocation lines based on current ownership percentages
            record._create_allocation_lines()
            
            record.state = 'calculated'
    
    def _create_allocation_lines(self):
        """Create allocation lines based on ownership percentages"""
        self.ensure_one()
        
        # Delete existing lines
        self.allocation_line_ids.unlink()
        
        # Get active ownership records during the allocation period
        ownership_records = self.env['equity.ownership'].search([
            ('company_id', '=', self.company_id.id),
            ('date_from', '<=', self.period_end),
            '|', ('date_to', '=', False), ('date_to', '>=', self.period_start),
        ])
        
        # Create allocation lines
        allocation_lines = []
        for ownership in ownership_records:
            # Calculate the portion of profit/loss for this owner
            amount = self.net_amount * (ownership.percentage / 100.0)
            
            allocation_lines.append((0, 0, {
                'partner_id': ownership.partner_id.id,
                'ownership_id': ownership.id,
                'percentage': ownership.percentage,
                'amount': amount,
                'equity_account_id': ownership.equity_account_id.id,
            }))
        
        self.write({'allocation_line_ids': allocation_lines})
    
    def action_post(self):
        """Post the allocation and create journal entries"""
        for record in self:
            if record.state != 'calculated':
                raise ValidationError(_("Only calculated allocations can be posted."))
            
            # Create the journal entry for the allocation
            move_vals = record._prepare_allocation_journal_entry()
            move = self.env['account.move'].create(move_vals)
            
            # Post the journal entry
            move.action_post()
            
            # Update allocation record
            record.write({
                'move_id': move.id,
                'state': 'posted'
            })
    
    def _prepare_allocation_journal_entry(self):
        """Prepare journal entry for profit/loss allocation"""
        self.ensure_one()
        
        move_lines = []
        
        # Get P&L accounts for the period
        income_accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('account_type', 'in', ['income', 'income_other'])
        ])
        
        expense_accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('account_type', 'in', ['expense', 'expense_direct_cost'])
        ])
        
        # Close income accounts (debit them)
        for income_acc in income_accounts:
            # Get the balance for this account during the period
            self.env.cr.execute("""
                SELECT SUM(balance) FROM account_move_line 
                WHERE account_id = %s 
                AND date >= %s 
                AND date <= %s 
                AND company_id = %s
                AND parent_state = 'posted'
            """, (income_acc.id, self.period_start, self.period_end, self.company_id.id))
            
            balance = self.env.cr.fetchone()[0] or 0.0
            if balance != 0:
                move_lines.append({
                    'name': f'Close Income: {income_acc.name}',
                    'account_id': income_acc.id,
                    'debit': 0.0,
                    'credit': abs(balance),
                    'currency_id': self.currency_id.id,
                })
        
        # Close expense accounts (credit them)
        for expense_acc in expense_accounts:
            # Get the balance for this account during the period
            self.env.cr.execute("""
                SELECT SUM(balance) FROM account_move_line 
                WHERE account_id = %s 
                AND date >= %s 
                AND date <= %s 
                AND company_id = %s
                AND parent_state = 'posted'
            """, (expense_acc.id, self.period_start, self.period_end, self.company_id.id))
            
            balance = self.env.cr.fetchone()[0] or 0.0
            if balance != 0:
                move_lines.append({
                    'name': f'Close Expense: {expense_acc.name}',
                    'account_id': expense_acc.id,
                    'debit': abs(balance),
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                })
        
        # Allocate net profit/loss to equity accounts
        for line in self.allocation_line_ids:
            if line.amount != 0:
                if line.amount > 0:  # Profit allocation
                    # Credit the equity account
                    move_lines.append({
                        'name': f'Profit Allocation to {line.partner_id.name}',
                        'account_id': line.equity_account_id.id,
                        'debit': 0.0,
                        'credit': line.amount,
                        'partner_id': line.partner_id.id,
                        'currency_id': self.currency_id.id,
                    })
                else:  # Loss allocation
                    # Debit the equity account
                    move_lines.append({
                        'name': f'Loss Allocation to {line.partner_id.name}',
                        'account_id': line.equity_account_id.id,
                        'debit': abs(line.amount),
                        'credit': 0.0,
                        'partner_id': line.partner_id.id,
                        'currency_id': self.currency_id.id,
                    })
        
        # Add to retained earnings if specified
        if self.retained_earnings_account_id:
            move_lines.append({
                'name': 'Retained Earnings Adjustment',
                'account_id': self.retained_earnings_account_id.id,
                'debit': 0.0 if self.net_amount >= 0 else abs(self.net_amount),
                'credit': self.net_amount if self.net_amount >= 0 else 0.0,
                'currency_id': self.currency_id.id,
            })
        
        # Create journal entry
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        
        return {
            'ref': f'P&L Allocation for {self.period_start} to {self.period_end}',
            'date': self.allocation_date,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'line_ids': [(0, 0, line) for line in move_lines],
            'equity_allocation_id': self.id,  # Link back to the allocation
        }
    
    def action_cancel(self):
        """Cancel the allocation"""
        for record in self:
            if record.state == 'posted' and record.move_id:
                # Reverse the journal entry
                reversal_wizard = self.env['account.move.reversal'].create({
                    'move_ids': [(4, record.move_id.id)],
                    'date': fields.Date.context_today(record),
                    'reason': 'Cancellation of P&L Allocation',
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
                record.write({
                    'move_id': False,
                    'state': 'draft'
                })
    
    @api.model
    def create(self, vals):
        """Override create to set name"""
        if vals.get('name', _('New Allocation')) == _('New Allocation'):
            vals['name'] = self.env['ir.sequence'].next_by_code('equity.allocation') or _('New Allocation')
        return super(EquityAllocation, self).create(vals)

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


class EquityAllocationLine(models.Model):
    _name = 'equity.allocation.line'
    _description = 'Profit & Loss Allocation Line'
    
    # Parent allocation
    allocation_id = fields.Many2one(
        'equity.allocation',
        string='Allocation',
        required=True,
        ondelete='cascade'
    )
    
    # Partner receiving the allocation
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        help='The equity owner receiving this allocation'
    )
    
    # Related ownership record
    ownership_id = fields.Many2one(
        'equity.ownership',
        string='Equity Ownership',
        required=True,
        help='The equity ownership record for this allocation'
    )
    
    # Percentage of allocation
    percentage = fields.Float(
        string='Percentage (%)',
        required=True,
        digits=(16, 4),
        help='Percentage of profit/loss allocated to this owner'
    )
    
    # Amount allocated
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        help='Calculated amount allocated to this owner'
    )
    
    # Equity account where the allocation is recorded
    equity_account_id = fields.Many2one(
        'account.account',
        string='Equity Account',
        required=True,
        help='The equity account where this allocation is recorded'
    )
    
    # Currency for monetary fields
    currency_id = fields.Many2one(
        'res.currency',
        related='allocation_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    @api.onchange('percentage')
    def _onchange_percentage(self):
        """Recalculate amount when percentage changes"""
        if self.allocation_id.net_amount and self.percentage:
            self.amount = self.allocation_id.net_amount * (self.percentage / 100.0)