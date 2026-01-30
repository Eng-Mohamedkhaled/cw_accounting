# -*- coding: utf-8 -*-
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