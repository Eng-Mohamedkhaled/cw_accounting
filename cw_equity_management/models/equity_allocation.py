# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, date


class EquityAllocation(models.Model):
    _name = 'equity.allocation'
    _description = 'Profit & Loss Allocation to Equity Owners'
    _order = 'allocation_date desc, id desc'
    _rec_name = 'name'
    
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
        default=lambda self: fields.Date.context_today(self),
        help='Date of the allocation'
    )
    
    from datetime import datetime, date

    # Period for which profit/loss is calculated
    period_start = fields.Date(
        string='Period Start',
        required=True,
        default=lambda self: date(date.today().year, 1, 1),
        help='Start date of the period for profit/loss calculation'
    )

    period_end = fields.Date(
        string='Period End',
        required=True,
        default=lambda self: fields.Date.context_today(self),
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
    move_name = fields.Char(
        string='Journal Entry Number',
        related='move_id.name',
        readonly=True
    )
    
    # Allocation lines showing how profit/loss is distributed
    allocation_line_ids = fields.One2many(
        'equity.allocation.line',
        'allocation_id',
        string='Allocation Lines',
        readonly=True
    )
    
    # Retained earnings account
    undistributed_profit_account_id = fields.Many2one(
        'account.account',
        string='Undistributed Profit Account',
        required=True,
        domain="[('company_ids', 'in', company_id), ('account_type', '=', 'equity_unaffected')]",
        help='Account for undistributed profit'
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
        """Calculate net profit/loss for the period using the existing custom P&L report"""
        from datetime import timedelta

        # Call the existing report to get the net profit/loss
        report_model = self.env['report.custom_account_move_line.profit_loss_report']

        # Prepare the data for the report
        # Format dates to ensure they include the full end date
        date_from_str = fields.Date.to_string(self.period_start)
        date_to_str = fields.Date.to_string(self.period_end)

        report_data = {
            'date_from': date_from_str,
            'date_to': date_to_str,
            'company_id': self.company_id.id
        }

        print(f"DEBUG: Calling P&L report with date_from={date_from_str}, date_to={date_to_str}")

        # Get the report values
        report_values = report_model._get_report_values([], data=report_data)

        # Extract the net profit from the report values
        # The report returns a 'lines' list, and the last line should be the net profit
        lines = report_values.get('lines', [])

        print(f"DEBUG: P&L report returned {len(lines)} lines")

        # Find the net profit line (the one with 'Net Profit' in the name)
        net_profit_line = None
        for line in lines:  # Look through all lines to find the Net Profit line
            print(f"DEBUG: Checking line: {line.get('account_name', 'N/A')} with balance: {line.get('balance', 0)}")
            if 'Net Profit' in str(line.get('account_name', '')) or 'net profit' in str(line.get('account_name', '')).lower():
                net_profit_line = line
                print(f"DEBUG: Found Net Profit line: {line}")
                break

        if net_profit_line:
            original_net_profit = net_profit_line.get('balance', 0.0)

            # Calculate the sum of balances for equity_unaffected accounts during the period
            equity_unaffected_accounts = self.env['account.account'].search([
                ('company_ids', 'in', self.company_id.id),
                ('account_type', '=', 'equity_unaffected')
            ])

            total_equity_unaffected_change = 0.0
            if equity_unaffected_accounts:
                # Query the account move lines for equity unaffected accounts during the period
                self.env.cr.execute("""
                    SELECT SUM(aml.balance) FROM account_move_line aml
                    JOIN account_account aa ON aml.account_id = aa.id
                    JOIN account_move am ON aml.move_id = am.id
                    WHERE aa.id IN %s
                    AND aml.date >= %s
                    AND aml.date <= %s
                    AND aml.company_id = %s
                    AND am.state = 'posted'
                """, (tuple(equity_unaffected_accounts.ids), self.period_start, self.period_end, self.company_id.id))

                result = self.env.cr.fetchone()[0]
                total_equity_unaffected_change = result or 0.0

                print(f"DEBUG: Total change in equity_unaffected accounts: {total_equity_unaffected_change}")

            adjusted_result = original_net_profit - total_equity_unaffected_change
            print(f"DEBUG: Original net profit: {original_net_profit}, Equity Unaffected Change: {total_equity_unaffected_change}, Adjusted result: {adjusted_result}")
            return adjusted_result
        else:
            print("DEBUG: Net Profit line not found, calculating manually")
            # If we can't find the net profit line, calculate it manually from the lines
            # Find all income and expense lines
            income_total = 0.0
            expense_total = 0.0

            for line in lines:
                if line.get('key') in ['income', 'other_income']:
                    income_value = line.get('balance', 0.0)
                    income_total += income_value
                    print(f"DEBUG: Income line '{line.get('account_name', 'N/A')}': {income_value}")
                elif line.get('key') in ['cogs', 'opex', 'other_exp', 'depr']:
                    expense_value = line.get('balance', 0.0)
                    expense_total += expense_value
                    print(f"DEBUG: Expense line '{line.get('account_name', 'N/A')}': {expense_value}")

            # Calculate the sum of balances for equity_unaffected accounts during the period
            equity_unaffected_accounts = self.env['account.account'].search([
                ('company_ids', 'in', self.company_id.id),
                ('account_type', '=', 'equity_unaffected')
            ])

            total_equity_unaffected_change = 0.0
            if equity_unaffected_accounts:
                # Query the account move lines for equity unaffected accounts during the period
                self.env.cr.execute("""
                    SELECT SUM(aml.balance) FROM account_move_line aml
                    JOIN account_account aa ON aml.account_id = aa.id
                    JOIN account_move am ON aml.move_id = am.id
                    WHERE aa.id IN %s
                    AND aml.date >= %s
                    AND aml.date <= %s
                    AND aml.company_id = %s
                    AND am.state = 'posted'
                """, (tuple(equity_unaffected_accounts.ids), self.period_start, self.period_end, self.company_id.id))

                result = self.env.cr.fetchone()[0]
                total_equity_unaffected_change = result or 0.0

                print(f"DEBUG: Total change in equity_unaffected accounts: {total_equity_unaffected_change}")

            manual_result = income_total - expense_total - total_equity_unaffected_change
            print(f"DEBUG: Manual calculation - Income: {income_total}, Expenses: {expense_total}, Equity Unaffected Change: {total_equity_unaffected_change}, Result: {manual_result}")
            return manual_result
    
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
        # An ownership is active during the period if:
        # - It belongs to the same company
        # - It started before or on the period end
        # - It either has no end date or ends after or on the period start
        ownership_domain = [
            ('company_id', '=', self.company_id.id),
            ('date_from', '<=', self.period_end),
            '|', ('date_to', '=', False), ('date_to', '>=', self.period_start),
        ]

        ownership_records = self.env['equity.ownership'].search(ownership_domain)

        # Debug: Print how many ownership records were found
        print(f"DEBUG: Found {len(ownership_records)} ownership records for allocation period {self.period_start} to {self.period_end}")

        # Create allocation lines
        allocation_lines = []
        for ownership in ownership_records:
            # Calculate the portion of profit/loss for this owner
            amount = self.net_amount * (ownership.percentage / 100.0)

            print(f"DEBUG: Creating allocation line for {ownership.partner_id.name}: {ownership.percentage}% of {self.net_amount} = {amount}")

            allocation_lines.append((0, 0, {
                'partner_id': ownership.partner_id.id,
                'ownership_id': ownership.id,
                'percentage': ownership.percentage,
                'amount': amount,
            }))

        print(f"DEBUG: Total allocation lines to create: {len(allocation_lines)}")

        if allocation_lines:
            self.write({'allocation_line_ids': allocation_lines})
        else:
            print("DEBUG: No allocation lines created - check if equity ownership records exist for this company and period")
    
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

        # Get the shared equity account from company settings
        shared_equity_account = self.company_id.equity_shared_account_id
        if not shared_equity_account:
            raise ValidationError(_("Please configure the shared equity account for company %s") % self.company_id.name)

        # Allocate net profit/loss to shared equity account with partner differentiation
        for line in self.allocation_line_ids:
            if line.amount != 0:
                if line.amount > 0:  # Profit allocation (credit shared equity account)
                    move_lines.append({
                        'name': f'Profit Allocation to {line.partner_id.name}',
                        'account_id': shared_equity_account.id,
                        'debit': 0.0,
                        'credit': line.amount,
                        'partner_id': line.partner_id.id,
                        'currency_id': self.currency_id.id,
                    })
                else:  # Loss allocation (debit shared equity account)
                    move_lines.append({
                        'name': f'Loss Allocation to {line.partner_id.name}',
                        'account_id': shared_equity_account.id,
                        'debit': abs(line.amount),
                        'credit': 0.0,
                        'partner_id': line.partner_id.id,
                        'currency_id': self.currency_id.id,
                    })

        # Adjust undistributed profit account
        if self.undistributed_profit_account_id:
            if self.net_amount >= 0:
                # Net profit: debit undistributed profit account
                move_lines.append({
                    'name': 'Undistributed Profit Adjustment',
                    'account_id': self.undistributed_profit_account_id.id,
                    'debit': self.net_amount,
                    'credit': 0.0,
                    'currency_id': self.currency_id.id,
                })
            else:
                # Net loss: credit undistributed profit account
                move_lines.append({
                    'name': 'Undistributed Profit Adjustment',
                    'account_id': self.undistributed_profit_account_id.id,
                    'debit': 0.0,
                    'credit': abs(self.net_amount),
                    'currency_id': self.currency_id.id,
                })

        # Create journal entry
        journal = self.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        return {
            'ref': f'Profit and Loss Allocation for {self.period_start} to {self.period_end}',
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
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set name"""
        for vals in vals_list:
            if vals.get('name', _('New Allocation')) == _('New Allocation'):
                vals['name'] = self.env['ir.sequence'].next_by_code('equity.allocation') or _('New Allocation')
        return super(EquityAllocation, self).create(vals_list)

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
    _rec_name = 'partner_id'
    
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
        digits=(16, 2),
        help='Percentage of profit/loss allocated to this owner'
    )
    
    # Amount allocated
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        help='Calculated amount allocated to this owner'
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
