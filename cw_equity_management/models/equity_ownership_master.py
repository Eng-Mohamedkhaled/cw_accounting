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
        'equity.ownership.line',
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
    
    @api.constrains('date_from', 'date_to', 'company_id')
    def _check_date_overlap(self):
        """Ensure no overlapping ownership structures for the same company"""
        for record in self:
            if record.date_to and record.date_from > record.date_to:
                raise ValidationError(_("Start date must be before end date."))
            
            # Find overlapping master structures
            overlapping_structures = self.search([
                ('id', '!=', record.id),
                ('company_id', '=', record.company_id.id),
                ('date_from', '<=', record.date_to or fields.Date.context_today(record)),
                ('date_to', '>=', record.date_from or fields.Date.context_today(record)),
                ('status', 'in', ['confirmed', 'active']),
            ])
            
            if overlapping_structures:
                raise ValidationError(_(
                    "There is an overlapping ownership structure for this company.\n"
                    "Conflicting structure(s): %s") % ', '.join(overlapping_structures.mapped('name')))
    
    def action_confirm(self):
        """Confirm the ownership structure"""
        for record in self:
            # Validate total percentage before confirming
            if abs(record.total_percentage - 100.0) > 0.01:
                raise ValidationError(_(
                    "Total ownership percentage must equal 100%% before confirming. "
                    "Current total: %.2f%%") % record.total_percentage)
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
        """Create individual ownership records from this master structure"""
        for record in self:
            if record.status not in ['confirmed', 'active']:
                raise ValidationError(_("Cannot create individual ownerships from a draft structure."))

            # Check if individual records already exist for this master structure
            existing_records = self.env['equity.ownership'].search([('master_id', '=', record.id)])
            if existing_records:
                raise ValidationError(_("Individual ownership records already exist for this master structure."))

            # Create individual ownership records and link them to the master structure
            for line in record.owners_line_ids:
                self.env['equity.ownership'].create({
                    'partner_id': line.partner_id.id,
                    'company_id': record.company_id.id,
                    'percentage': line.percentage,
                    'equity_account_id': line.equity_account_id.id,
                    'date_from': record.date_from,
                    'date_to': record.date_to,
                    'master_id': record.id,  # Link to master structure to bypass validation
                })
    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.name} - {record.company_id.name} ({record.total_percentage}%)"
            result.append((record.id, name))
        return result


class EquityOwnershipLine(models.Model):
    _name = 'equity.ownership.line'
    _description = 'Equity Ownership Line'
    _order = 'sequence, id'
    
    master_id = fields.Many2one(
        'equity.ownership.master',
        string='Master Structure',
        required=True,
        ondelete='cascade',
        help='Parent ownership structure'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of this ownership line in the structure'
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        required=True,
        domain=[('is_equity_owner', '=', True)],
        help='The partner who owns the equity'
    )
    
    percentage = fields.Float(
        string='Ownership Percentage (%)',
        required=True,
        default=0.0,
        digits=(16, 4),
        help='Percentage of ownership (0-100%)'
    )
    
    equity_account_id = fields.Many2one(
        'account.account',
        string='Equity Account',
        required=True,
        help='The equity account where this ownership is recorded'
    )
    
    @api.constrains('percentage')
    def _check_percentage_range(self):
        """Ensure percentage is between 0 and 100"""
        for record in self:
            if record.percentage < 0 or record.percentage > 100:
                raise ValidationError(_("Ownership percentage must be between 0 and 100%."))
    
    @api.constrains('master_id', 'percentage')
    def _check_master_percentage_limit(self):
        """Ensure the sum of percentages in the master doesn't exceed 100%"""
        for record in self:
            total = sum(line.percentage for line in record.master_id.owners_line_ids)
            if total > 100:
                raise ValidationError(_(
                    "Total ownership percentage in the structure exceeds 100%%. "
                    "Current total: %.2f%%") % total)