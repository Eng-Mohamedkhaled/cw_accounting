# Comprehensive Documentation: Owners' Equity Management Module

## Overview
The Owners' Equity Management module provides a complete solution for managing equity ownership, capital transactions, and profit/loss allocation in Odoo. It includes both individual ownership management and a master structure approach for handling multiple owners.

## Module Components

### 1. Partner Extension (`models/partner.py`)
Extends the standard partner model to include equity owner functionality.

```python
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Add equity owner role flag
    is_equity_owner = fields.Boolean(
        string='Is Equity Owner',
        help='Check this box if this partner is an equity owner.'
    )
    
    # One-to-many relationship to equity ownership records
    equity_ownership_ids = fields.One2many(
        'equity.ownership', 
        'partner_id', 
        string='Equity Ownership Records',
        help='List of equity ownership records for this partner'
    )
    
    # Computed field to show current ownership percentage in the current company
    current_equity_percentage = fields.Float(
        compute='_compute_current_equity_percentage',
        string='Current Equity Percentage',
        store=False,
        help='Current equity percentage in the current company'
    )
    
    @api.depends('equity_ownership_ids')
    def _compute_current_equity_percentage(self):
        """Compute the current equity percentage for the current company"""
        for partner in self:
            current_ownership = self.env['equity.ownership'].search([
                ('partner_id', '=', partner.id),
                ('company_id', '=', self.env.company.id),
                ('date_from', '<=', fields.Date.context_today(self)),
                '|', ('date_to', '=', False), ('date_to', '>=', fields.Date.context_today(self))
            ], limit=1)
            
            partner.current_equity_percentage = current_ownership.percentage if current_ownership else 0.0
    
    def action_view_equity_ownership(self):
        """Action to view equity ownership records"""
        action = self.env["ir.actions.actions"]._for_xml_id("cw_equity_management.action_equity_ownership")
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action
```

### 2. Individual Equity Ownership (`models/equity_ownership.py`)
Manages individual ownership records with validation and tracking.

```python
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class EquityOwnership(models.Model):
    _name = 'equity.ownership'
    _description = 'Equity Ownership Record'
    _order = 'date_from desc, partner_id'
    
    # Partner who owns the equity
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        ondelete='cascade',
        domain=[('is_equity_owner', '=', True)],
        help='The partner who owns the equity'
    )
    
    # Company where the ownership applies
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='The company where this ownership applies'
    )
    
    # Ownership percentage
    percentage = fields.Float(
        string='Ownership Percentage (%)',
        required=True,
        default=0.0,
        digits=(16, 4),
        help='Percentage of ownership (0-100%)'
    )
    
    # Equity account where the ownership is recorded
    equity_account_id = fields.Many2one(
        'account.account',
        string='Equity Account',
        required=True,
        help='The equity account where this ownership is recorded'
    )
    
    # Time period for the ownership
    date_from = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        help='Start date of the ownership period'
    )
    
    date_to = fields.Date(
        string='End Date',
        help='End date of the ownership period (leave empty for ongoing)'
    )
    
    # Computed field for status
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('future', 'Future')
    ], string='Status', compute='_compute_status', store=True)
    
    # Total capital contributed by this owner
    total_contributions = fields.Monetary(
        compute='_compute_total_contributions',
        string='Total Contributions',
        currency_field='currency_id',
        help='Total capital contributions made by this owner'
    )
    
    # Total withdrawals by this owner
    total_withdrawals = fields.Monetary(
        compute='_compute_total_withdrawals',
        string='Total Withdrawals',
        currency_field='currency_id',
        help='Total withdrawals made by this owner'
    )
    
    # Currency for monetary fields
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
        readonly=True
    )
    
    # Link to master ownership structure (for bypassing individual validation)
    master_id = fields.Many2one(
        'equity.ownership.master',
        string='Master Structure',
        help='Link to the master ownership structure that manages this ownership'
    )

    @api.constrains('percentage')
    def _check_percentage_range(self):
        """Ensure percentage is between 0 and 100"""
        for record in self:
            if record.percentage < 0 or record.percentage > 100:
                raise ValidationError(_("Ownership percentage must be between 0 and 100%."))
    
    @api.constrains('date_from', 'date_to', 'partner_id', 'company_id')
    def _check_date_overlap(self):
        """Ensure no overlapping ownership periods for the same partner and company"""
        for record in self:
            if record.date_to and record.date_from > record.date_to:
                raise ValidationError(_("Start date must be before end date."))
            
            # Find overlapping records
            overlapping_records = self.search([
                ('id', '!=', record.id),
                ('partner_id', '=', record.partner_id.id),
                ('company_id', '=', record.company_id.id),
                ('date_from', '<=', record.date_to or fields.Date.context_today(record)),
                ('date_to', '>=', record.date_from or fields.Date.context_today(record)),
            ])
            
            if overlapping_records:
                raise ValidationError(_(
                    "There is an overlapping ownership period for this partner in this company.\n"
                    "Conflicting record(s): %s") % ', '.join(overlapping_records.mapped('partner_id.name'))
                )
    
    @api.constrains('company_id', 'percentage')
    def _check_total_ownership_percentage(self):
        """Ensure total ownership percentage equals 100% per company when not part of a master structure"""
        for record in self:
            # Skip validation if this record is part of a master structure
            # The validation will be handled at the master level
            if record.master_id:
                continue
                
            # Calculate total percentage for this company during the period
            total_percentage = 0.0
            current_date = fields.Date.context_today(record)
            
            # Get all active ownership records for this company during the period
            # Exclude the current record if it's already saved (has an id)
            domain = [
                ('company_id', '=', record.company_id.id),
                ('date_from', '<=', record.date_to or current_date),
                ('master_id', '=', False),  # Only consider records not part of master structure
                '|', ('date_to', '=', False), ('date_to', '>=', record.date_from or current_date),
            ]
            
            # If the record is already saved, exclude it from the search
            if record.id:
                domain = [('id', '!=', record.id)] + domain
                # Get all other active records and add the current record's percentage
                other_records = self.search(domain)
                for ownership in other_records:
                    total_percentage += ownership.percentage
                total_percentage += record.percentage
            else:
                # For new records, get all existing records and add the current record's percentage
                other_records = self.search(domain)
                for ownership in other_records:
                    total_percentage += ownership.percentage
                total_percentage += record.percentage

            # Allow slight tolerance for rounding errors
            if abs(total_percentage - 100.0) > 0.01:
                raise ValidationError(_(
                    "Total ownership percentage for company '%s' must equal 100%%. "
                    "Current total: %.2f%%") % (record.company_id.name, total_percentage)
                )
    
    @api.constrains('equity_account_id', 'company_id')
    def _check_equity_account_company(self):
        """Ensure equity account belongs to the same company"""
        for record in self:
            if record.company_id not in record.equity_account_id.company_ids:
                raise ValidationError(_(
                    "The equity account must belong to the same company as the ownership record."
                ))
    
    @api.depends('date_from', 'date_to')
    def _compute_status(self):
        """Compute the status based on dates"""
        today = fields.Date.context_today(self)
        for record in self:
            if record.date_to and record.date_to < today:
                record.status = 'expired'
            elif record.date_from > today:
                record.status = 'future'
            else:
                record.status = 'active'
    
    def _compute_total_contributions(self):
        """Compute total contributions for this owner"""
        for record in self:
            contributions = self.env['equity.transaction'].search([
                ('partner_id', '=', record.partner_id.id),
                ('company_id', '=', record.company_id.id),
                ('transaction_type', '=', 'contribution'),
                ('state', '=', 'posted')
            ])
            record.total_contributions = sum(contributions.mapped('amount'))
    
    def _compute_total_withdrawals(self):
        """Compute total withdrawals for this owner"""
        for record in self:
            withdrawals = self.env['equity.transaction'].search([
                ('partner_id', '=', record.partner_id.id),
                ('company_id', '=', record.company_id.id),
                ('transaction_type', '=', 'withdrawal'),
                ('state', '=', 'posted')
            ])
            record.total_withdrawals = sum(withdrawals.mapped('amount'))
    
    @api.model
    def create(self, vals):
        """Override create to ensure proper ownership percentage validation"""
        result = super(EquityOwnership, self).create(vals)
        
        # Validate total ownership percentage after creation
        result._check_total_ownership_percentage()
        
        return result
    
    def write(self, vals):
        """Override write to ensure proper ownership percentage validation"""
        result = super(EquityOwnership, self).write(vals)
        
        # Validate total ownership percentage after update
        self._check_total_ownership_percentage()
        
        return result
    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.partner_id.name} - {record.percentage}% ({record.company_id.name})"
            if record.date_to:
                name += f" ({record.date_from} to {record.date_to})"
            else:
                name += f" (since {record.date_from})"
            result.append((record.id, name))
        return result

    def action_view_equity_transactions(self):
        """Action to view equity transactions for this ownership"""
        action = self.env["ir.actions.actions"]._for_xml_id("cw_equity_management.action_equity_transaction")
        action['domain'] = [
            ('partner_id', '=', self.partner_id.id),
            ('company_id', '=', self.company_id.id)
        ]
        action['context'] = {
            'default_partner_id': self.partner_id.id,
            'default_company_id': self.company_id.id
        }
        return action
```

### 3. Master Ownership Structure (`models/equity_ownership_master.py`)
Centralized management of multiple owners for a company.

```python
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class EquityOwnershipMaster(models.Model):
    _name = 'equity.ownership.master'
    _description = 'Master Equity Ownership Structure'
    _order = 'name, id'
    
    name = fields.Char(
        string='Structure Name',
        required=True,
        default=lambda self: _('New Master Structure'),
        help='Name for this ownership structure'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company for which this ownership structure applies'
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', required=True,
       help='Status of the ownership structure')
    
    total_percentage = fields.Float(
        compute='_compute_total_percentage',
        string='Total Percentage',
        store=True,
        digits=(16, 4),
        help='Total ownership percentage for this structure'
    )
    
    owners_line_ids = fields.One2many(
        'equity.ownership',
        'master_id',
        string='Ownership Lines',
        help='Individual ownership records for this structure'
    )
    
    date_from = fields.Date(
        string='Effective From',
        help='Date when this ownership structure becomes effective'
    )
    
    date_to = fields.Date(
        string='Effective To',
        help='Date when this ownership structure expires'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this ownership structure'
    )
    
    @api.depends('owners_line_ids.percentage')
    def _compute_total_percentage(self):
        """Compute total percentage for the ownership structure"""
        for record in self:
            record.total_percentage = sum(line.percentage for line in record.owners_line_ids)
    
    @api.constrains('total_percentage', 'owners_line_ids')
    def _check_total_percentage(self):
        """Ensure total percentage equals 100% when structure is confirmed"""
        for record in self:
            if record.status in ['confirmed', 'active']:
                if abs(record.total_percentage - 100.0) > 0.01:
                    raise ValidationError(_(
                        "Total ownership percentage must equal 100%% when structure is confirmed. "
                        "Current total: %.2f%%") % record.total_percentage)
    
    @api.constrains('owners_line_ids')
    def _check_ownership_lines_validity(self):
        """Ensure ownership lines have valid data"""
        for record in self:
            for line in record.owners_line_ids:
                if line.percentage < 0 or line.percentage > 100:
                    raise ValidationError(_(
                        "Ownership percentage must be between 0 and 100%%. "
                        "Partner: %s has invalid percentage: %.2f%%") %
                        (line.partner_id.name, line.percentage))

                if not line.partner_id:
                    raise ValidationError(_(
                        "Each ownership line must have a partner assigned."))

                if not line.equity_account_id:
                    raise ValidationError(_(
                        "Each ownership line must have an equity account assigned. Partner: %s") %
                        line.partner_id.name)

    @api.constrains('date_from', 'date_to', 'company_id')
    def _check_date_overlap(self):
        """Ensure only one master ownership structure per company"""
        for record in self:
            if record.date_to and record.date_from > record.date_to:
                raise ValidationError(_("Start date must be before end date."))

            # Find other master structures for the same company
            other_structures = self.search([
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id),
            ])

            if other_structures:
                raise ValidationError(_(
                    "A master ownership structure already exists for company '%s'.\n"
                    "Only one master structure is allowed per company.\n"
                    "Existing structure(s): %s") %
                    (record.company_id.name, ', '.join(other_structures.mapped('name'))))

    def action_confirm(self):
        """Confirm the ownership structure"""
        for record in self:
            # Validate total percentage before confirming
            if abs(record.total_percentage - 100.0) > 0.01:
                raise ValidationError(_(
                    "Total ownership percentage must equal 100%% before confirming. "
                    "Current total: %.2f%%") % record.total_percentage)

            # Ensure there are ownership lines
            if not record.owners_line_ids:
                raise ValidationError(_("Cannot confirm a master structure without any ownership lines."))

            record.status = 'confirmed'
    
    def action_activate(self):
        """Activate the ownership structure"""
        for record in self:
            record.status = 'active'
    
    def action_draft(self):
        """Reset to draft status"""
        for record in self:
            record.status = 'draft'
    
    def action_archive(self):
        """Archive the ownership structure"""
        for record in self:
            record.status = 'archived'
    
    def action_create_individual_ownerships(self):
        """This method is no longer needed since ownership records are now directly linked to master."""
        # In the new design, the ownership records are already linked to the master structure
        # This method is kept for compatibility but doesn't need to do anything
        pass
    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.name} - {record.company_id.name} ({record.total_percentage}%)"
            result.append((record.id, name))
        return result


### 4. Equity Transactions (`models/equity_transaction.py`)
Handles capital contributions and withdrawals.

```python
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
        
        # Determine accounts based on transaction type
        equity_account = self.ownership_id.equity_account_id
        cash_account = self.cash_account_id
        
        # Prepare move lines
        move_lines = []
        
        if self.transaction_type == 'contribution':
            # For contribution: debit cash, credit equity
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
            # For withdrawal: debit equity, credit cash
            move_lines.extend([
                {
                    'name': f'Capital Withdrawal to {self.partner_id.name}',
                    'account_id': equity_account.id,
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
```

### 5. Equity Allocation (`models/equity_allocation.py`)
Handles profit and loss allocation to owners.

```python
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
    undistributed_profit_account_id = fields.Many2one(
        'account.account',
        string='Undistributed Profit Account',
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
        
        # Adjust undistributed profit account
        if self.undistributed_profit_account_id:
            move_lines.append({
                'name': 'Undistributed Profit Adjustment',
                'account_id': self.undistributed_profit_account_id.id,
                'debit': self.net_amount if self.net_amount >= 0 else 0.0,
                'credit': 0.0 if self.net_amount >= 0 else abs(self.net_amount),
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
```

### 6. Account Move Extension (`models/account_move.py`)
Links equity transactions and allocations to journal entries.

```python
# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # Link to equity transaction for tracking purposes
    equity_transaction_id = fields.Many2one(
        'equity.transaction',
        string='Equity Transaction',
        help='Link to the equity transaction that generated this journal entry'
    )
    
    # Link to equity allocation for tracking purposes
    equity_allocation_id = fields.Many2one(
        'equity.allocation',
        string='Equity Allocation',
        help='Link to the equity allocation that generated this journal entry'
    )
```

## Key Features

### 1. Master Ownership Structure
- Centralized management of multiple owners for a company
- Direct One2Many relationship to equity ownership records (no intermediate model)
- Flexible setup with draft stage (validates data but not 100% total)
- Validation when confirming (requires 100% total)
- Only one master structure allowed per company
- Links individual records to master structure to bypass individual validation

### 2. Individual Ownership Management
- Traditional approach for single owners
- Strict 100% validation for standalone records
- Date range management
- Partner-specific equity tracking

### 3. Capital Transactions
- Contributions and withdrawals
- Automatic journal entry generation
- Proper debit/credit logic
- State management (draft/posted/cancelled)

### 4. Profit & Loss Allocation
- Period-based allocation
- Automatic distribution by ownership percentage
- Journal entry generation
- Retained earnings handling

### 5. Security & Access Control
- Multi-company support
- Proper access rights
- Data isolation between companies

## Usage Workflow

### For Multiple Owners (Recommended):
1. Create a master ownership structure
2. Add multiple owners with their respective percentages directly in the ownership lines
3. Each ownership line is validated for proper data (partner, equity account, percentage range)
4. Confirm when total reaches 100% and structure is ready for use
5. Only one master structure is allowed per company
6. Perform transactions and allocations normally

### For Single Owners (Legacy Support):
1. Create individual ownership record directly
2. Ensure total ownership equals 100% immediately
3. Perform transactions and allocations normally

## Validation Rules
- Ownership percentages must be between 0-100%
- No overlapping ownership periods
- Total ownership must equal 100% when structure is confirmed
- Individual records bypass validation if linked to master structure
- Transaction dates must be within ownership period
- All accounting entries properly balanced

This module provides a comprehensive solution for equity management with flexibility for both simple and complex ownership structures.