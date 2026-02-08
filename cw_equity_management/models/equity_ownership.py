# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class EquityOwnership(models.Model):
    _name = 'equity.ownership'
    _description = 'Equity Ownership Record'
    _order = 'date_from desc, partner_id'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

        
    name = fields.Char(
        string='Ownership Name',
        compute='_compute_name',
        store=True

    )

    @api.depends('partner_id', 'percentage', 'date_from', 'date_to')
    def _compute_name(self):
        """Compute the name based on partner and percentage"""
        for record in self:
            name = f"{record.partner_id.name} - {record.percentage}%"
            if record.date_to:
                name += f" ({record.date_from} to {record.date_to})"
            else:
                name += f" (since {record.date_from})"
            record.name = name
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
        string='Ownership Percentage',
        required=True,
        default=0.0,
        digits=(16, 2),
        help='Percentage of ownership (0-100%)'
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
    
    master_id = fields.Many2one(
        'equity.ownership.master',
        string='Master Structure',
        help='Link to the master ownership structure that manages this ownership'
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
        """Compute total contributions for this owner from actual journal entries"""
        for record in self:
            # Get company's shared equity account
            equity_account = record.company_id.equity_shared_account_id
            
            if equity_account:
                # Query account move lines for this partner in the equity account
                # Credits increase equity (contributions), debits decrease equity
                self.env.cr.execute("""
                    SELECT SUM(aml.credit - aml.debit)
                    FROM account_move_line aml
                    JOIN account_move am ON aml.move_id = am.id
                    WHERE aml.partner_id = %s
                      AND aml.account_id = %s
                      AND aml.company_id = %s
                      AND am.state = 'posted'
                """, (record.partner_id.id, equity_account.id, record.company_id.id))

                result = self.env.cr.fetchone()[0]
                record.total_contributions = result or 0.0
            else:
                record.total_contributions = 0.0

    def _compute_total_withdrawals(self):
        """Compute total withdrawals for this owner from actual journal entries"""
        for record in self:
            # Get company's shared drawing account
            drawing_account = record.company_id.drawing_shared_account_id
            
            if drawing_account:
                # Query account move lines for this partner in the drawing account
                # Debits increase drawings (negative impact on equity), credits decrease drawings (positive impact)
                # For withdrawals, we want the net effect on equity
                self.env.cr.execute("""
                    SELECT SUM(aml.debit - aml.credit)
                    FROM account_move_line aml
                    JOIN account_move am ON aml.move_id = am.id
                    WHERE aml.partner_id = %s
                      AND aml.account_id = %s
                      AND aml.company_id = %s
                      AND am.state = 'posted'
                """, (record.partner_id.id, drawing_account.id, record.company_id.id))

                result = self.env.cr.fetchone()[0]
                record.total_withdrawals = result or 0.0
            else:
                record.total_withdrawals = 0.0
    
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
