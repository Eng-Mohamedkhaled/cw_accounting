# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime


class EquityOwnershipMaster(models.Model):
    _name = 'equity.ownership.master'
    _description = 'Master Equity Ownership Structure'
    _order = 'name, id'
    _rec_name = 'name'
    
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
        digits=(16, 2),
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

    
    def name_get(self):
        """Custom name display"""
        result = []
        for record in self:
            name = f"{record.name} - {record.company_id.name} ({record.total_percentage}%)"
            result.append((record.id, name))
        return result
